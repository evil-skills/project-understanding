/**
 * Type definitions for the API.
 * @module types
 */

/**
 * @typedef {Object} User
 * @property {string} id - User ID
 * @property {string} name - User name
 * @property {string} email - User email
 * @property {Date} createdAt - Creation date
 * @property {boolean} isActive - Active status
 */

/**
 * @typedef {Object} Product
 * @property {string} id - Product ID
 * @property {string} name - Product name
 * @property {number} price - Product price
 * @property {string[]} tags - Product tags
 */

/**
 * @typedef {Object} Order
 * @property {string} id - Order ID
 * @property {string} userId - User ID
 * @property {Product[]} products - Ordered products
 * @property {number} total - Total amount
 * @property {string} status - Order status
 */

module.exports = {};
