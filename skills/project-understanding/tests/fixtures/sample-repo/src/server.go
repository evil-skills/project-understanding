package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gorilla/mux"
)

// Config holds application configuration
type Config struct {
	Host string
	Port int
}

// Server represents the HTTP server
type Server struct {
	router *mux.Router
	config Config
	srv    *http.Server
}

// NewServer creates a new server instance
func NewServer(cfg Config) *Server {
	s := &Server{
		router: mux.NewRouter(),
		config: cfg,
	}
	s.routes()
	return s
}

// routes sets up all routes
func (s *Server) routes() {
	s.router.HandleFunc("/health", s.healthHandler).Methods("GET")
	s.router.HandleFunc("/api/v1/items", s.listItemsHandler).Methods("GET")
	s.router.HandleFunc("/api/v1/items/{id}", s.getItemHandler).Methods("GET")
	s.router.HandleFunc("/api/v1/items", s.createItemHandler).Methods("POST")
	s.router.HandleFunc("/api/v1/items/{id}", s.updateItemHandler).Methods("PUT")
	s.router.HandleFunc("/api/v1/items/{id}", s.deleteItemHandler).Methods("DELETE")
}

// healthHandler handles health check requests
func (s *Server) healthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	fmt.Fprintf(w, `{"status":"ok","time":"%s"}`, time.Now().Format(time.RFC3339))
}

// listItemsHandler returns all items
func (s *Server) listItemsHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	// TODO: Implement database query
	fmt.Fprint(w, `{"items":[]}`)
}

// getItemHandler returns a single item
func (s *Server) getItemHandler(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	id := vars["id"]
	
	w.Header().Set("Content-Type", "application/json")
	fmt.Fprintf(w, `{"id":"%s"}`, id)
}

// createItemHandler creates a new item
func (s *Server) createItemHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	fmt.Fprint(w, `{"message":"created"}`)
}

// updateItemHandler updates an existing item
func (s *Server) updateItemHandler(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	id := vars["id"]
	
	w.Header().Set("Content-Type", "application/json")
	fmt.Fprintf(w, `{"id":"%s","message":"updated"}`, id)
}

// deleteItemHandler deletes an item
func (s *Server) deleteItemHandler(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusNoContent)
}

// Start begins listening for requests
func (s *Server) Start() error {
	addr := fmt.Sprintf("%s:%d", s.config.Host, s.config.Port)
	
	s.srv = &http.Server{
		Addr:         addr,
		Handler:      s.router,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 15 * time.Second,
		IdleTimeout:  60 * time.Second,
	}
	
	log.Printf("Starting server on %s", addr)
	return s.srv.ListenAndServe()
}

// Shutdown gracefully stops the server
func (s *Server) Shutdown(ctx context.Context) error {
	return s.srv.Shutdown(ctx)
}

func main() {
	cfg := Config{
		Host: "0.0.0.0",
		Port: 8080,
	}
	
	server := NewServer(cfg)
	
	// Handle graceful shutdown
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	
	go func() {
		if err := server.Start(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Server error: %v", err)
		}
	}()
	
	<-sigChan
	log.Println("Shutting down server...")
	
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	
	if err := server.Shutdown(ctx); err != nil {
		log.Fatalf("Server forced to shutdown: %v", err)
	}
	
	log.Println("Server exited")
}
