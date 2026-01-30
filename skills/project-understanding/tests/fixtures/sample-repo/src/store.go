package main

import (
	"database/sql"
	"fmt"
	"time"

	_ "github.com/mattn/go-sqlite3"
)

// Item represents a data item
type Item struct {
	ID        int64     `json:"id"`
	Name      string    `json:"name"`
	Value     float64   `json:"value"`
	CreatedAt time.Time `json:"created_at"`
}

// ItemStore handles database operations for items
type ItemStore struct {
	db *sql.DB
}

// NewItemStore creates a new item store
func NewItemStore(db *sql.DB) *ItemStore {
	return &ItemStore{db: db}
}

// CreateTable creates the items table
func (s *ItemStore) CreateTable() error {
	query := `
	CREATE TABLE IF NOT EXISTS items (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		name TEXT NOT NULL,
		value REAL,
		created_at DATETIME DEFAULT CURRENT_TIMESTAMP
	)`
	_, err := s.db.Exec(query)
	return err
}

// Create inserts a new item
func (s *ItemStore) Create(item *Item) error {
	result, err := s.db.Exec(
		"INSERT INTO items (name, value) VALUES (?, ?)",
		item.Name, item.Value,
	)
	if err != nil {
		return err
	}
	
	id, err := result.LastInsertId()
	if err != nil {
		return err
	}
	
	item.ID = id
	return nil
}

// Get retrieves an item by ID
func (s *ItemStore) Get(id int64) (*Item, error) {
	item := &Item{}
	err := s.db.QueryRow(
		"SELECT id, name, value, created_at FROM items WHERE id = ?", id,
	).Scan(&item.ID, &item.Name, &item.Value, &item.CreatedAt)
	
	if err == sql.ErrNoRows {
		return nil, fmt.Errorf("item not found: %d", id)
	}
	
	return item, err
}

// List retrieves all items
func (s *ItemStore) List() ([]*Item, error) {
	rows, err := s.db.Query("SELECT id, name, value, created_at FROM items ORDER BY id")
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	
	var items []*Item
	for rows.Next() {
		item := &Item{}
		err := rows.Scan(&item.ID, &item.Name, &item.Value, &item.CreatedAt)
		if err != nil {
			return nil, err
		}
		items = append(items, item)
	}
	
	return items, rows.Err()
}

// Update modifies an existing item
func (s *ItemStore) Update(item *Item) error {
	_, err := s.db.Exec(
		"UPDATE items SET name = ?, value = ? WHERE id = ?",
		item.Name, item.Value, item.ID,
	)
	return err
}

// Delete removes an item
func (s *ItemStore) Delete(id int64) error {
	_, err := s.db.Exec("DELETE FROM items WHERE id = ?", id)
	return err
}

// Close closes the database connection
func (s *ItemStore) Close() error {
	return s.db.Close()
}
