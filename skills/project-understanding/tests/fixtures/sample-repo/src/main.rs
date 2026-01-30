//! Main application entry point and core types.
//! 
//! This module defines the primary application structure and
//! initialization logic for the Rust-based API server.

use std::sync::Arc;
use tokio::sync::RwLock;
use serde::{Deserialize, Serialize};

/// Application configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Config {
    /// Server host address
    pub host: String,
    /// Server port
    pub port: u16,
    /// Database connection string
    pub database_url: String,
    /// Enable debug mode
    pub debug: bool,
}

impl Default for Config {
    fn default() -> Self {
        Config {
            host: "127.0.0.1".to_string(),
            port: 8080,
            database_url: "postgres://localhost/app".to_string(),
            debug: false,
        }
    }
}

/// Application state shared across handlers
pub struct AppState {
    /// Application configuration
    pub config: Config,
    /// Request counter
    pub request_count: RwLock<u64>,
}

impl AppState {
    /// Create new application state
    pub fn new(config: Config) -> Arc<Self> {
        Arc::new(Self {
            config,
            request_count: RwLock::new(0),
        })
    }
    
    /// Increment and return request count
    pub async fn increment_counter(&self) -> u64 {
        let mut count = self.request_count.write().await;
        *count += 1;
        *count
    }
}

/// User entity
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct User {
    /// Unique identifier
    pub id: uuid::Uuid,
    /// Username
    pub username: String,
    /// Email address
    pub email: String,
    /// Account creation timestamp
    pub created_at: chrono::DateTime<chrono::Utc>,
    /// Active status
    pub is_active: bool,
}

impl User {
    /// Create a new user
    pub fn new(username: String, email: String) -> Self {
        User {
            id: uuid::Uuid::new_v4(),
            username,
            email,
            created_at: chrono::Utc::now(),
            is_active: true,
        }
    }
    
    /// Deactivate user account
    pub fn deactivate(&mut self) {
        self.is_active = false;
    }
    
    /// Activate user account
    pub fn activate(&mut self) {
        self.is_active = true;
    }
}

/// API response wrapper
#[derive(Debug, Serialize, Deserialize)]
pub struct ApiResponse<T> {
    /// Response status
    pub success: bool,
    /// Response data
    pub data: Option<T>,
    /// Error message if applicable
    pub error: Option<String>,
}

impl<T> ApiResponse<T> {
    /// Create successful response
    pub fn success(data: T) -> Self {
        ApiResponse {
            success: true,
            data: Some(data),
            error: None,
        }
    }
    
    /// Create error response
    pub fn error(message: impl Into<String>) -> Self {
        ApiResponse {
            success: false,
            data: None,
            error: Some(message.into()),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_user_creation() {
        let user = User::new("testuser".to_string(), "test@example.com".to_string());
        assert_eq!(user.username, "testuser");
        assert!(user.is_active);
    }
    
    #[test]
    fn test_user_deactivation() {
        let mut user = User::new("test".to_string(), "test@test.com".to_string());
        user.deactivate();
        assert!(!user.is_active);
    }
    
    #[test]
    fn test_api_response_success() {
        let response = ApiResponse::success("data");
        assert!(response.success);
        assert_eq!(response.data, Some("data"));
        assert!(response.error.is_none());
    }
    
    #[test]
    fn test_api_response_error() {
        let response = ApiResponse::<String>::error("Something went wrong");
        assert!(!response.success);
        assert!(response.data.is_none());
        assert_eq!(response.error, Some("Something went wrong".to_string()));
    }
}
