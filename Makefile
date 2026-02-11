.PHONY: help help-web test demo build install clean

# ─── Default target ──────────────────────────────────────────────
help: ## Show this help message
	@echo ""
	@echo "  Locker — Android-based service lockdown for Ubuntu"
	@echo ""
	@echo "  Usage:  make <target>"
	@echo ""
	@echo "  Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "    \033[96m%-14s\033[0m %s\n", $$1, $$2}'
	@echo ""

# ─── Serve HTML documentation via local web server ──────────────────
help-web: ## Serve the HTML documentation on http://0.0.0.0:8888
	@echo ""
	@echo "  Serving documentation at:"
	@printf "    \033[96mhttp://localhost:8888/documentation.html\033[0m\n"
	@printf "    \033[96mhttp://$$(hostname -I | awk '{print $$1}'):8888/documentation.html\033[0m\n"
	@echo ""
	@echo "  Press Ctrl+C to stop."
	@echo ""
	@python3 -m http.server 8888 --directory docs

# ─── Run unit tests ───────────────────────────────────────────────
test: ## Run the full unit test suite
	python3 -W default::ResourceWarning -m pytest tests/ -v

# ─── Build the .deb package ──────────────────────────────────────
build: ## Build the .deb package
	scripts/build-deb.sh

# ─── Install the .deb package ────────────────────────────────────
install: build ## Build and install the .deb package
	@cp locker_1.0.0-1_all.deb /tmp/locker_1.0.0-1_all.deb
	sudo apt install -y /tmp/locker_1.0.0-1_all.deb
	@rm -f /tmp/locker_1.0.0-1_all.deb

# ─── Clean everything ────────────────────────────────────────────
clean: ## Stop service, uninstall package, and remove build artifacts
	@echo "Stopping locker service..."
	@sudo systemctl stop locker 2>/dev/null || true
	@echo "Removing locker package..."
	@sudo apt remove -y locker 2>/dev/null || true
	@echo "Cleaning build artifacts..."
	@rm -f locker_1.0.0-1_all.deb
	@rm -rf .pybuild debian/locker debian/.debhelper
	@rm -f debian/debhelper-build-stamp debian/files debian/locker.substvars
	@echo "Done."

# ─── Run the interactive demo ────────────────────────────────────
demo: ## Run the interactive end-to-end demo (uses Makefile.demo)
	@$(MAKE) -f Makefile.demo demo
