use crate::types::{StrategyMode, StrategyRuntime};

pub struct StrategyLifecycleManager {
    runtimes: Vec<StrategyRuntime>,
}

pub enum GraduationError {
    NotFound,
}

impl StrategyLifecycleManager {
    pub fn load_runtime(&self, id: &str) -> Option<&StrategyRuntime> {
        self.runtimes.iter().find(|r| r.id == id)
    }

    pub fn current_mode(&self) -> StrategyMode {
        StrategyMode::Paper
    }
}
