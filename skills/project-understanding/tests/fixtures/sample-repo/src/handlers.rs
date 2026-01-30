//! HTTP request handlers and routing logic.
//!
//! This module contains all request handlers organized by resource type.

use axum::{
    extract::{Path, State},
    http::StatusCode,
    response::Json,
    routing::{get, post, put, delete},
    Router,
};
use std::sync::Arc;

use crate::{AppState, ApiResponse, User};

/// Create router with all routes
pub fn create_router(state: Arc<AppState>) -> Router {
    Router::new()
        .route("/health", get(health_check))
        .route("/api/users", get(list_users).post(create_user))
        .route("/api/users/:id", get(get_user).put(update_user).delete(delete_user))
        .with_state(state)
}

/// Health check endpoint
async fn health_check(State(state): State<Arc<AppState>>) -> Json<ApiResponse<serde_json::Value>> {
    let count = state.increment_counter().await;
    let response = serde_json::json!({
        "status": "ok",
        "requests_handled": count,
    });
    Json(ApiResponse::success(response))
}

/// List all users
async fn list_users() -> Json<ApiResponse<Vec<User>>> {
    // TODO: Implement database query
    let users: Vec<User> = vec![];
    Json(ApiResponse::success(users))
}

/// Get user by ID
async fn get_user(Path(id): Path<String>) -> Result<Json<ApiResponse<User>>, StatusCode> {
    // TODO: Implement database query
    Err(StatusCode::NOT_IMPLEMENTED)
}

/// Create new user
async fn create_user(Json(user): Json<User>) -> Result<Json<ApiResponse<User>>, StatusCode> {
    // TODO: Implement database insert
    Ok(Json(ApiResponse::success(user)))
}

/// Update existing user
async fn update_user(
    Path(id): Path<String>,
    Json(user): Json<User>,
) -> Result<Json<ApiResponse<User>>, StatusCode> {
    // TODO: Implement database update
    Ok(Json(ApiResponse::success(user)))
}

/// Delete user
async fn delete_user(Path(id): Path<String>) -> StatusCode {
    // TODO: Implement database delete
    StatusCode::NO_CONTENT
}

/// Request logging middleware
pub async fn log_request<B>(
    req: axum::http::Request<B>,
    next: axum::middleware::Next<B>,
) -> axum::response::Response {
    let path = req.uri().path().to_string();
    let method = req.method().to_string();
    
    let response = next.run(req).await;
    
    let status = response.status();
    tracing::info!("{} {} - {}", method, path, status);
    
    response
}
