/**
 * Main API module for handling HTTP requests.
 * @module api
 */

const express = require('express');
const { validateRequest, formatResponse } = require('./middleware');
const { UserService } = require('./services');
const logger = require('./logger');

/**
 * Create and configure Express application
 * @returns {Express.Application} Configured Express app
 */
function createApp() {
    const app = express();
    
    // Middleware
    app.use(express.json());
    app.use(express.urlencoded({ extended: true }));
    
    // Routes
    app.get('/api/health', healthCheck);
    app.get('/api/users', listUsers);
    app.get('/api/users/:id', getUser);
    app.post('/api/users', createUser);
    app.put('/api/users/:id', updateUser);
    app.delete('/api/users/:id', deleteUser);
    
    // Error handling
    app.use(errorHandler);
    
    return app;
}

/**
 * Health check endpoint
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 */
function healthCheck(req, res) {
    res.json({ status: 'ok', timestamp: new Date().toISOString() });
}

/**
 * List all users
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 * @param {Function} next - Express next middleware function
 */
async function listUsers(req, res, next) {
    try {
        const users = await UserService.findAll();
        res.json(formatResponse(users));
    } catch (error) {
        next(error);
    }
}

/**
 * Get user by ID
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 * @param {Function} next - Express next middleware function
 */
async function getUser(req, res, next) {
    try {
        const { id } = req.params;
        const user = await UserService.findById(id);
        
        if (!user) {
            return res.status(404).json({ error: 'User not found' });
        }
        
        res.json(formatResponse(user));
    } catch (error) {
        next(error);
    }
}

/**
 * Create new user
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 * @param {Function} next - Express next middleware function
 */
async function createUser(req, res, next) {
    try {
        const data = validateRequest(req.body, ['name', 'email']);
        const user = await UserService.create(data);
        res.status(201).json(formatResponse(user));
    } catch (error) {
        next(error);
    }
}

/**
 * Update existing user
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 * @param {Function} next - Express next middleware function
 */
async function updateUser(req, res, next) {
    try {
        const { id } = req.params;
        const user = await UserService.update(id, req.body);
        res.json(formatResponse(user));
    } catch (error) {
        next(error);
    }
}

/**
 * Delete user
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 * @param {Function} next - Express next middleware function
 */
async function deleteUser(req, res, next) {
    try {
        const { id } = req.params;
        await UserService.delete(id);
        res.status(204).send();
    } catch (error) {
        next(error);
    }
}

/**
 * Global error handler
 * @param {Error} err - Error object
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 * @param {Function} next - Express next middleware function
 */
function errorHandler(err, req, res, next) {
    logger.error('Error:', err.message);
    
    const status = err.status || 500;
    const message = err.message || 'Internal server error';
    
    res.status(status).json({ error: message });
}

module.exports = { createApp, healthCheck, listUsers, getUser, createUser, updateUser, deleteUser };
