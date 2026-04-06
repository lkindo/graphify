const std = @import("std");
const mem = @import("std").mem;

const Config = struct {
    name: []const u8,
    value: u32,

    pub fn init(name: []const u8, value: u32) Config {
        return Config{ .name = name, .value = value };
    }

    pub fn getName(self: Config) []const u8 {
        return self.name;
    }
};

const Status = enum {
    active,
    inactive,
};

fn processData(cfg: Config) void {
    const name = cfg.getName();
    _ = name;
}

fn createConfig() Config {
    const cfg = Config.init("test", 42);
    processData(cfg);
    return cfg;
}

pub fn main() void {
    const cfg = createConfig();
    _ = cfg;
}
