/**
 * AST instrumentation: parse JS source with acorn, walk the AST, and emit
 * instrumented source that calls __trace(line, () => ({x, y, z})) at every
 * statement boundary. The closure captures the calling function's scope,
 * letting the runtime snapshot all visible locals.
 *
 * Scope tracking:
 *   - Walk each function's body, tracking declared var names (var/let/const + params).
 *   - At each trace point, emit an arrow returning an object literal of all
 *     currently-in-scope names (union of all enclosing scopes).
 *
 * Also injects __enterFrame / __exitFrame at function entry/exit and __op()
 * on call expressions for the operation counter.
 */
import { parse } from "acorn";
import type { Node } from "acorn";
import { generate } from "astring";

export const RUNTIME_NAMES = {
  trace: "__trace",
  op: "__op",
  enterFrame: "__enterFrame",
  exitFrame: "__exitFrame",
  log: "__log",
};

const RUNTIME_SET = new Set(Object.values(RUNTIME_NAMES));

export type InstrumentResult = {
  code: string;
};

type MutableNode = Node & {
  type: string;
  [key: string]: unknown;
};

/** Parse + instrument. Throws SyntaxError with message on parse failure. */
export function instrument(source: string): InstrumentResult {
  const ast = parse(source, {
    ecmaVersion: 2022,
    sourceType: "script",
    locations: true,
  }) as unknown as MutableNode;

  transformProgram(ast);

  const code = generate(ast as unknown as Parameters<typeof generate>[0]);
  return { code };
}

// ─── Scope tracking ────────────────────────────────────────────────────────

type Scope = {
  /** Variables visible at this level (including hoisted). */
  vars: Set<string>;
  /** Function name (or null for block scopes). */
  fnName: string | null;
  /** Parameters (for function scopes). */
  params: string[];
};

type ScopeStack = Scope[];

function newFunctionScope(fnName: string, params: string[]): Scope {
  return { vars: new Set(params), fnName, params };
}

function newBlockScope(): Scope {
  return { vars: new Set(), fnName: null, params: [] };
}

/** Collect all var names visible from the top of the stack (all enclosing scopes). */
function visibleVars(stack: ScopeStack): string[] {
  const seen = new Set<string>();
  for (const scope of stack) {
    for (const v of scope.vars) seen.add(v);
  }
  return Array.from(seen);
}

/** Hoist var/function declarations in a block BEFORE walking. */
function hoist(stmts: MutableNode[], scope: Scope): void {
  for (const s of stmts) {
    if (s.type === "FunctionDeclaration") {
      const fn = s as unknown as { id: { name: string } };
      if (fn.id?.name) scope.vars.add(fn.id.name);
    } else if (s.type === "VariableDeclaration") {
      const kind = (s as unknown as { kind: string }).kind;
      if (kind === "var") {
        const decls = (s as unknown as { declarations: Array<{ id: { name?: string } }> }).declarations;
        for (const d of decls) {
          if (d.id?.name) scope.vars.add(d.id.name);
        }
      }
    }
  }
}

// ─── Transform ─────────────────────────────────────────────────────────────

function transformProgram(root: MutableNode): void {
  const globalScope: Scope = {
    vars: new Set(),
    fnName: "<global>",
    params: [],
  };
  const stack: ScopeStack = [globalScope];

  if (Array.isArray(root.body)) {
    hoist(root.body as MutableNode[], globalScope);
    root.body = instrumentBlock(root.body as MutableNode[], stack);
  }
}

/**
 * Instrument a list of statements. Returns a NEW array with trace injections.
 * `stack` must already have the enclosing scope pushed.
 */
function instrumentBlock(body: MutableNode[], stack: ScopeStack): MutableNode[] {
  const out: MutableNode[] = [];

  for (const stmt of body) {
    // Collect let/const decls into current scope BEFORE the trace
    // (but only the names — their values don't exist yet).
    if (stmt.type === "VariableDeclaration") {
      const kind = (stmt as unknown as { kind: string }).kind;
      if (kind === "let" || kind === "const") {
        const decls = (stmt as unknown as { declarations: Array<{ id: { name?: string } }> }).declarations;
        for (const d of decls) {
          if (d.id?.name) stack[stack.length - 1].vars.add(d.id.name);
        }
      }
    }

    // Trace BEFORE executing the statement
    const line = (stmt as unknown as { loc?: { start: { line: number } } }).loc?.start.line ?? 0;
    out.push(makeTraceCall(line, visibleVars(stack)));

    // Recurse into statement
    transformStatement(stmt, stack);
    out.push(stmt);
  }

  return out;
}

function transformStatement(stmt: MutableNode, stack: ScopeStack): void {
  switch (stmt.type) {
    case "FunctionDeclaration":
    case "FunctionExpression":
    case "ArrowFunctionExpression":
      transformFunction(stmt, stack);
      return;

    case "BlockStatement": {
      const scope = newBlockScope();
      stack.push(scope);
      const body = stmt.body as MutableNode[];
      hoist(body, scope);
      stmt.body = instrumentBlock(body, stack);
      stack.pop();
      return;
    }

    case "IfStatement": {
      const n = stmt as unknown as { consequent: MutableNode; alternate: MutableNode | null; test: MutableNode };
      ensureBlock(stmt, "consequent");
      if (n.alternate) ensureBlock(stmt, "alternate");
      transformStatement(n.consequent, stack);
      if (n.alternate) transformStatement(n.alternate, stack);
      transformExpression(n.test, stack);
      return;
    }

    case "WhileStatement":
    case "DoWhileStatement": {
      const n = stmt as unknown as { body: MutableNode; test: MutableNode };
      ensureBlock(stmt, "body");
      transformStatement(n.body, stack);
      transformExpression(n.test, stack);
      return;
    }

    case "ForStatement": {
      const n = stmt as unknown as { init: MutableNode | null; test: MutableNode | null; update: MutableNode | null; body: MutableNode };
      // for (let i=0; ...) — `i` is visible to body; push a block scope
      const scope = newBlockScope();
      stack.push(scope);
      if (n.init && n.init.type === "VariableDeclaration") {
        const kind = (n.init as unknown as { kind: string }).kind;
        const decls = (n.init as unknown as { declarations: Array<{ id: { name?: string } }> }).declarations;
        for (const d of decls) {
          if (d.id?.name && (kind === "let" || kind === "const" || kind === "var")) {
            scope.vars.add(d.id.name);
          }
        }
      }
      ensureBlock(stmt, "body");
      transformStatement(n.body, stack);
      if (n.test) transformExpression(n.test, stack);
      if (n.update) transformExpression(n.update, stack);
      stack.pop();
      return;
    }

    case "ForOfStatement":
    case "ForInStatement": {
      const n = stmt as unknown as { left: MutableNode; right: MutableNode; body: MutableNode };
      const scope = newBlockScope();
      stack.push(scope);
      if (n.left && n.left.type === "VariableDeclaration") {
        const decls = (n.left as unknown as { declarations: Array<{ id: { name?: string } }> }).declarations;
        for (const d of decls) {
          if (d.id?.name) scope.vars.add(d.id.name);
        }
      }
      ensureBlock(stmt, "body");
      transformStatement(n.body, stack);
      transformExpression(n.right, stack);
      stack.pop();
      return;
    }

    case "TryStatement": {
      const n = stmt as unknown as { block: MutableNode; handler: MutableNode | null; finalizer: MutableNode | null };
      transformStatement(n.block, stack);
      if (n.handler) {
        const hn = n.handler as unknown as { param: { name?: string } | null; body: MutableNode };
        const scope = newBlockScope();
        stack.push(scope);
        if (hn.param?.name) scope.vars.add(hn.param.name);
        transformStatement(hn.body, stack);
        stack.pop();
      }
      if (n.finalizer) transformStatement(n.finalizer, stack);
      return;
    }

    case "ExpressionStatement": {
      const n = stmt as unknown as { expression: MutableNode };
      transformExpression(n.expression, stack);
      return;
    }

    case "ReturnStatement": {
      const n = stmt as unknown as { argument: MutableNode | null };
      if (n.argument) transformExpression(n.argument, stack);
      return;
    }

    case "VariableDeclaration": {
      const n = stmt as unknown as { declarations: Array<{ init: MutableNode | null }> };
      for (const d of n.declarations) {
        if (d.init) transformExpression(d.init, stack);
      }
      return;
    }

    case "ThrowStatement": {
      const n = stmt as unknown as { argument: MutableNode | null };
      if (n.argument) transformExpression(n.argument, stack);
      return;
    }

    case "SwitchStatement": {
      const n = stmt as unknown as { discriminant: MutableNode; cases: Array<{ consequent: MutableNode[] }> };
      transformExpression(n.discriminant, stack);
      for (const c of n.cases) {
        // Each case's statements are instrumented inline (no new scope)
        c.consequent = instrumentBlock(c.consequent, stack);
      }
      return;
    }

    default:
      // Descend into unknown nodes' children
      walkChildren(stmt, (child) => transformStatement(child, stack));
      return;
  }
}

/**
 * Transform an expression: recurse into children. Currently we don't wrap
 * calls for op-counting here (handled via future enhancement if needed);
 * the runtime also counts statement boundaries.
 */
function transformExpression(expr: MutableNode | null, stack: ScopeStack): void {
  if (!expr) return;

  if (
    expr.type === "FunctionExpression" ||
    expr.type === "ArrowFunctionExpression"
  ) {
    transformFunction(expr, stack);
    return;
  }

  // Don't double-wrap runtime calls
  if (expr.type === "CallExpression") {
    const callee = (expr as unknown as { callee: MutableNode & { name?: string } }).callee;
    if (callee.type === "Identifier" && callee.name && RUNTIME_SET.has(callee.name)) {
      return;
    }
  }

  walkChildren(expr, (child) => transformExpression(child, stack));
}

function transformFunction(fn: MutableNode, stack: ScopeStack): void {
  const fnNode = fn as unknown as {
    id: { name?: string } | null;
    params: Array<{ name?: string; type?: string }>;
    body: MutableNode;
  };
  const name = fnNode.id?.name ?? "<anon>";
  const params = (fnNode.params ?? [])
    .map((p) => ("name" in p ? p.name : undefined))
    .filter((n): n is string => typeof n === "string");

  // Arrow fn with expression body → wrap in block with return
  if (fnNode.body && fnNode.body.type !== "BlockStatement") {
    const expr = fnNode.body;
    fnNode.body = {
      type: "BlockStatement",
      body: [{ type: "ReturnStatement", argument: expr } as unknown as MutableNode],
    } as unknown as MutableNode;
  }

  const scope = newFunctionScope(name, params);
  stack.push(scope);

  // Hoist + instrument body
  const body = fnNode.body.body as MutableNode[];
  hoist(body, scope);

  // Build instrumented body: __enterFrame at start, then instrumented stmts,
  // wrapped in try/finally so __exitFrame always runs.
  const instrumented = instrumentBlock(body, stack);

  fnNode.body.body = [
    makeEnterFrameCall(name, params),
    {
      type: "TryStatement",
      block: { type: "BlockStatement", body: instrumented } as unknown as MutableNode,
      handler: null,
      finalizer: {
        type: "BlockStatement",
        body: [makeExitFrameCall()],
      } as unknown as MutableNode,
    } as unknown as MutableNode,
  ];

  stack.pop();
}

// ─── Helpers ──────────────────────────────────────────────────────────────

function walkChildren(node: MutableNode, visit: (child: MutableNode) => void): void {
  for (const key of Object.keys(node)) {
    if (key === "loc" || key === "start" || key === "end" || key === "range" || key === "type") continue;
    const child = (node as Record<string, unknown>)[key];
    if (Array.isArray(child)) {
      for (const c of child) {
        if (c && typeof c === "object" && "type" in c) visit(c as MutableNode);
      }
    } else if (child && typeof child === "object" && "type" in child) {
      visit(child as MutableNode);
    }
  }
}

function ensureBlock(node: MutableNode, key: string): void {
  const child = (node as Record<string, unknown>)[key] as MutableNode | null | undefined;
  if (!child) return;
  if (child.type !== "BlockStatement") {
    (node as Record<string, unknown>)[key] = {
      type: "BlockStatement",
      body: [child],
    } as unknown as MutableNode;
  }
}

/**
 * Build:  __trace(line, () => ({ x, y, z }))
 */
function makeTraceCall(line: number, varNames: string[]): MutableNode {
  const props = varNames.map((name) => ({
    type: "Property",
    key: { type: "Identifier", name },
    value: { type: "Identifier", name },
    kind: "init",
    method: false,
    shorthand: true,
    computed: false,
  }));

  return {
    type: "ExpressionStatement",
    expression: {
      type: "CallExpression",
      callee: { type: "Identifier", name: RUNTIME_NAMES.trace },
      arguments: [
        { type: "Literal", value: line, raw: String(line) },
        {
          type: "ArrowFunctionExpression",
          id: null,
          params: [],
          body: {
            type: "ObjectExpression",
            properties: props,
          },
          async: false,
          expression: true,
        },
      ],
      optional: false,
    },
  } as unknown as MutableNode;
}

function makeEnterFrameCall(name: string, params: string[]): MutableNode {
  return {
    type: "ExpressionStatement",
    expression: {
      type: "CallExpression",
      callee: { type: "Identifier", name: RUNTIME_NAMES.enterFrame },
      arguments: [
        { type: "Literal", value: name, raw: JSON.stringify(name) },
        {
          type: "ArrayExpression",
          elements: params.map((p) => ({
            type: "Literal",
            value: p,
            raw: JSON.stringify(p),
          })),
        },
        {
          type: "ArrayExpression",
          elements: params.map((p) => ({ type: "Identifier", name: p })),
        },
      ],
      optional: false,
    },
  } as unknown as MutableNode;
}

function makeExitFrameCall(): MutableNode {
  return {
    type: "ExpressionStatement",
    expression: {
      type: "CallExpression",
      callee: { type: "Identifier", name: RUNTIME_NAMES.exitFrame },
      arguments: [],
      optional: false,
    },
  } as unknown as MutableNode;
}
