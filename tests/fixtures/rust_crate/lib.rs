// Multi-file Rust crate fixture for testing cross-file `use crate::*` resolution.
// Structure mirrors a typical Rust workspace crate:
//     lib.rs      — re-exports sibling modules with `pub use`
//     types.rs    — type definitions (StrategyMode, StrategyRuntime)
//     manager.rs  — imports types via `use crate::types::{...}`
//     helper.rs   — imports types via single-ident `use crate::types::StrategyMode`

pub use manager::{GraduationError, StrategyLifecycleManager};
pub use types::{StrategyMode, StrategyRuntime};

pub mod types;
pub mod manager;
pub mod helper;
