.PHONY: help help-web test demo build install clean

MOCK_SERIAL = mockup_data_118s9Zas
SERIALS_FILE = /etc/locker/connect_android_serials.json

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
	sudo scripts/build-deb.sh

# ─── Install the .deb package ────────────────────────────────────
install: build ## Build and install the .deb package
	sudo apt install -y ./locker_1.0.0-1_all.deb

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

# ═══════════════════════════════════════════════════════════════════
#  ANSI color codes
# ═══════════════════════════════════════════════════════════════════
RESET    := \033[0m
BOLD     := \033[1m
DIM      := \033[2m

TEAL     := \033[96m
RED      := \033[91m
BRED     := \033[1;91m
YELLOW   := \033[93m
GREEN    := \033[92m

# ═══════════════════════════════════════════════════════════════════
#  End-to-end demo  —  run with:  make demo
# ═══════════════════════════════════════════════════════════════════

# Pause — wait for the user to press ENTER
define PAUSE
	@printf "\n$(DIM)  ─── Press ENTER to continue ───$(RESET) " && read _pause
endef

# Section header
define HEADER
	@echo ""
	@printf "$(BOLD)$(TEAL)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(RESET)\n"
	@printf "$(BOLD)$(TEAL)  %s$(RESET)\n" $(1)
	@printf "$(BOLD)$(TEAL)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(RESET)\n"
	@echo ""
endef

# Show a sudo command, ask for ENTER, then execute it.
# Usage: $(call SUDO_CMD,<command to display and run>)
define SUDO_CMD
	@printf "\n  $(YELLOW)The following command requires elevated privileges:$(RESET)\n"
	@printf "  $(BOLD)$(TEAL)$$ sudo $(1)$(RESET)\n"
	@printf "  $(DIM)Press ENTER to authorize and run ───$(RESET) " && read _auth
	@sudo $(1)
endef

demo: ## Run the interactive end-to-end demo
	@echo ""
	@printf "$(BOLD)$(TEAL)╔══════════════════════════════════════════════════════════════╗$(RESET)\n"
	@printf "$(BOLD)$(TEAL)║                                                            ║$(RESET)\n"
	@printf "$(BOLD)$(TEAL)║              LOCKER  —  End-to-End Demo                    ║$(RESET)\n"
	@printf "$(BOLD)$(TEAL)║                                                            ║$(RESET)\n"
	@printf "$(BOLD)$(TEAL)║$(RESET)   Protect your server. Lock services when your Android     $(BOLD)$(TEAL)║$(RESET)\n"
	@printf "$(BOLD)$(TEAL)║$(RESET)   device is disconnected. Unlock them when it returns.     $(BOLD)$(TEAL)║$(RESET)\n"
	@printf "$(BOLD)$(TEAL)║                                                            ║$(RESET)\n"
	@printf "$(BOLD)$(TEAL)╚══════════════════════════════════════════════════════════════╝$(RESET)\n"
	@echo ""
	@printf "  $(DIM)This demo will walk you through the complete Locker workflow.$(RESET)\n"
	@printf "  $(DIM)Each step that requires sudo will ask for your approval.$(RESET)\n"
	@printf "  $(DIM)Press ENTER at each pause to advance to the next step.$(RESET)\n"
	$(PAUSE)

	@# ── Step 0: Validate service is running ──────────────────────
	$(call HEADER,"Step 0 — Verifying the Locker service is running")
	@printf "  $(DIM)Locker runs as a systemd service in the background,$(RESET)\n"
	@printf "  $(DIM)continuously monitoring your Android device connection.$(RESET)\n"
	@printf "  $(DIM)Let's check if it's alive.$(RESET)\n"
	@printf "\n  $(YELLOW)The following command requires elevated privileges:$(RESET)\n"
	@printf "  $(BOLD)$(TEAL)$$ sudo systemctl is-active locker$(RESET)\n"
	@printf "  $(DIM)Press ENTER to authorize and run ───$(RESET) " && read _auth
	@sudo systemctl is-active locker \
		&& printf "  $(GREEN)✓ Service is active.$(RESET)\n" \
		|| ( \
			printf "  $(YELLOW)⚠ Service not running — attempting to start...$(RESET)\n" \
			&& sudo systemctl start locker \
			&& sleep 2 \
			&& printf "  $(GREEN)✓ Service started.$(RESET)\n" \
		) || ( \
			printf "  $(RED)✗ Failed to start the locker service.$(RESET)\n" \
			&& printf "  $(RED)  Run: sudo systemctl status locker$(RESET)\n" \
			&& printf "  $(RED)  You may need to rebuild and reinstall: make install$(RESET)\n" \
			&& exit 1 \
		)
	$(PAUSE)

	@# ── Step 1: Ensure permissive mode ───────────────────────────
	$(call HEADER,"Step 1 — Setting mode to PERMISSIVE (safe starting point)")
	@printf "  $(DIM)Permissive mode means Locker monitors your device connection$(RESET)\n"
	@printf "  $(DIM)but does NOT stop any services. Think of it as 'dry-run' mode.$(RESET)\n"
	@printf "  $(DIM)We start here so nothing gets disrupted while we configure.$(RESET)\n"
	$(call SUDO_CMD,locker set-mode permissive)
	@echo ""
	@printf "  $(GREEN)✓ Mode is now permissive — safe to configure.$(RESET)\n"
	$(PAUSE)

	@# ── Log the demo start ───────────────────────────────────────
	@echo ""
	@printf "$(BOLD)$(TEAL)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(RESET)\n"
	@printf "$(BOLD)$(TEAL)         >>>  STARTING END-TO-END DEMO  <<<                  $(RESET)\n"
	@printf "$(BOLD)$(TEAL)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(RESET)\n"
	@echo ""
	$(PAUSE)

	@# ── Step 2: Remove existing services ─────────────────────────
	$(call HEADER,"Step 2 — Clearing any previously configured services")
	@printf "  $(DIM)Before we start fresh, let's remove all managed services.$(RESET)\n"
	@printf "  $(DIM)This only removes them from Locker's watchlist —$(RESET)\n"
	@printf "  $(DIM)the actual services on the system are untouched.$(RESET)\n"
	@echo ""
	@printf "  $(TEAL)$$ locker list-services$(RESET)\n"
	@locker list-services || true
	@echo ""
	@printf "  $(DIM)Removing all configured services...$(RESET)\n"
	@for svc in $$(python3 -c "import json; c=json.load(open('/etc/locker/config.json')); [print(s) for s in c.get('services',[])]" 2>/dev/null); do \
		printf "\n  $(YELLOW)The following command requires elevated privileges:$(RESET)\n"; \
		printf "  $(BOLD)$(TEAL)\$$ sudo locker remove-service $$svc$(RESET)\n"; \
		printf "  $(DIM)Press ENTER to authorize and run ───$(RESET) " && read _auth; \
		sudo locker remove-service $$svc 2>/dev/null || true; \
		echo ""; \
	done
	@printf "  $(TEAL)$$ locker list-services$(RESET)\n"
	@locker list-services || true
	@echo ""
	@printf "  $(GREEN)✓ Service list is now empty.$(RESET)\n"
	$(PAUSE)

	@# ── Step 3: Add services ─────────────────────────────────────
	$(call HEADER,"Step 3 — Adding services to protect: cron, ssh, and sshd")
	@printf "  $(DIM)We'll tell Locker to manage 'cron', 'ssh', and 'sshd'.$(RESET)\n"
	@printf "  $(DIM)When the configured Android device is disconnected, Locker$(RESET)\n"
	@printf "  $(DIM)will stop these services. When it reconnects — they start back up.$(RESET)\n"
	$(call SUDO_CMD,locker add-service cron)
	$(call SUDO_CMD,locker add-service ssh)
	$(call SUDO_CMD,locker add-service sshd)
	@echo ""
	@printf "  $(TEAL)$$ locker list-services$(RESET)\n"
	@locker list-services
	@echo ""
	@printf "  $(GREEN)✓ cron, ssh, and sshd are now managed by Locker.$(RESET)\n"
	$(PAUSE)

	@# ── Step 4: Configure the Android device serial ──────────────
	$(call HEADER,"Step 4 — Configuring the Android device serial")
	@printf "  $(DIM)Locker uses a specific Android device as your physical 'key'.$(RESET)\n"
	@printf "  $(DIM)Only when this device is connected will services stay running.$(RESET)\n"
	@printf "  $(DIM)We'll set the serial to our demo device: $(BOLD)$(MOCK_SERIAL)$(RESET)\n"
	$(call SUDO_CMD,locker set-android-serial $(MOCK_SERIAL))
	@echo ""
	@printf "  $(TEAL)$$ locker get-android-serial$(RESET)\n"
	@locker get-android-serial
	@echo ""
	@printf "  $(GREEN)✓ Device serial configured.$(RESET)\n"
	$(PAUSE)

	@# ── Step 5: Place the connected serials file ─────────────────
	$(call HEADER,"Step 5 — Simulating device connection")
	@printf "  $(DIM)For this demo we don't need a physical phone.$(RESET)\n"
	@printf "  $(DIM)Locker checks for a file at:$(RESET)\n"
	@printf "  $(BOLD)  $(SERIALS_FILE)$(RESET)\n"
	@echo ""
	@printf "  $(DIM)If the file exists, is valid JSON, and its 'android_serial'$(RESET)\n"
	@printf "  $(DIM)value matches the configured serial — the device is treated$(RESET)\n"
	@printf "  $(DIM)as connected. Let's create it now.$(RESET)\n"
	$(call SUDO_CMD,bash -c 'echo '"'"'{"android_serial": "$(MOCK_SERIAL)"}'"'"' > $(SERIALS_FILE)')
	@printf "  $(GREEN)✓ Connected serials file created — device is now 'connected'.$(RESET)\n"
	$(PAUSE)

	@# ── Step 6: Switch to ENFORCING mode ─────────────────────────
	$(call HEADER,"Step 6 — Switching to ENFORCING mode")
	@printf "  $(DIM)This is the moment of truth. In enforcing mode, Locker$(RESET)\n"
	@printf "  $(DIM)will $(BOLD)actively stop$(RESET)$(DIM) services when the device is gone,$(RESET)\n"
	@printf "  $(DIM)and $(BOLD)automatically start$(RESET)$(DIM) them when it comes back.$(RESET)\n"
	$(call SUDO_CMD,locker set-mode enforcing)
	@echo ""
	@printf "  $(GREEN)✓ Enforcing mode active. Locker is now protecting your services.$(RESET)\n"
	$(PAUSE)

	@# ── Step 7: Show current status (expect: active) ─────────────
	$(call HEADER,"Step 7 — Current status (device 'connected')")
	@printf "  $(DIM)The connected serials file is present, so Locker sees the$(RESET)\n"
	@printf "  $(DIM)device as connected. Services should be RUNNING.$(RESET)\n"
	@echo ""
	@printf "  $(YELLOW)Waiting for the service to pick up the config...$(RESET)\n"
	@sleep 7
	@echo ""
	@printf "  $(TEAL)$$ locker list-services$(RESET)\n"
	@locker list-services
	@echo ""
	@printf "  $(TEAL)$$ systemctl is-active cron$(RESET)\n"
	@systemctl is-active cron && printf "  $(GREEN)→ cron: active$(RESET)\n" || printf "  $(RED)→ cron: inactive (unexpected!)$(RESET)\n"
	@printf "  $(TEAL)$$ systemctl is-active ssh$(RESET)\n"
	@systemctl is-active ssh && printf "  $(GREEN)→ ssh:  active$(RESET)\n" || printf "  $(RED)→ ssh:  inactive (unexpected!)$(RESET)\n"
	@printf "  $(TEAL)$$ systemctl is-active sshd$(RESET)\n"
	@systemctl is-active sshd && printf "  $(GREEN)→ sshd: active$(RESET)\n" || printf "  $(RED)→ sshd: inactive (unexpected!)$(RESET)\n"
	@echo ""
	@printf "  $(GREEN)✓ All services are running — device is 'connected'.$(RESET)\n"
	$(PAUSE)

	@# ── Step 8: Simulate device disconnection (expect: inactive) ─
	$(call HEADER,"Step 8 — Simulating device DISCONNECTION")
	@printf "  $(DIM)Now we remove the connected serials file. This simulates$(RESET)\n"
	@printf "  $(DIM)unplugging the Android device from the server.$(RESET)\n"
	$(call SUDO_CMD,rm -f $(SERIALS_FILE))
	@printf "  $(GREEN)✓ File removed — device is now 'disconnected'.$(RESET)\n"
	@echo ""
	@printf "  $(YELLOW)Waiting for Locker to detect the disconnection...$(RESET)\n"
	@sleep 7
	@echo ""
	@printf "  $(TEAL)$$ locker list-services$(RESET)\n"
	@locker list-services
	@echo ""
	@printf "  $(TEAL)$$ systemctl is-active cron$(RESET)\n"
	@systemctl is-active cron && printf "  $(RED)→ cron: active (Locker should have stopped it!)$(RESET)\n" || printf "  $(GREEN)→ cron: inactive$(RESET)\n"
	@printf "  $(TEAL)$$ systemctl is-active ssh$(RESET)\n"
	@systemctl is-active ssh && printf "  $(RED)→ ssh:  active (Locker should have stopped it!)$(RESET)\n" || printf "  $(GREEN)→ ssh:  inactive$(RESET)\n"
	@printf "  $(TEAL)$$ systemctl is-active sshd$(RESET)\n"
	@systemctl is-active sshd && printf "  $(RED)→ sshd: active (Locker should have stopped it!)$(RESET)\n" || printf "  $(GREEN)→ sshd: inactive$(RESET)\n"
	@echo ""
	@printf "  $(GREEN)✓ Services have been STOPPED by Locker. The system is locked down.$(RESET)\n"
	$(PAUSE)

	@# ── Step 9: Try to start them manually (expect: inactive) ────
	$(call HEADER,"Step 9 — Can someone restart the services manually?")
	@printf "  $(DIM)Let's say an attacker (or a curious admin) tries to$(RESET)\n"
	@printf "  $(DIM)start cron, ssh, and sshd manually. Will they stay up?$(RESET)\n"
	$(call SUDO_CMD,systemctl start cron)
	$(call SUDO_CMD,systemctl start ssh)
	$(call SUDO_CMD,systemctl start sshd)
	@echo ""
	@printf "  $(DIM)Services started manually. Let's wait and see what happens...$(RESET)\n"
	@sleep 7
	@echo ""
	@printf "  $(TEAL)$$ systemctl is-active cron$(RESET)\n"
	@systemctl is-active cron && printf "  $(RED)→ cron: active (Locker should have stopped it!)$(RESET)\n" || printf "  $(GREEN)→ cron: inactive$(RESET)\n"
	@printf "  $(TEAL)$$ systemctl is-active ssh$(RESET)\n"
	@systemctl is-active ssh && printf "  $(RED)→ ssh:  active (Locker should have stopped it!)$(RESET)\n" || printf "  $(GREEN)→ ssh:  inactive$(RESET)\n"
	@printf "  $(TEAL)$$ systemctl is-active sshd$(RESET)\n"
	@systemctl is-active sshd && printf "  $(RED)→ sshd: active (Locker should have stopped it!)$(RESET)\n" || printf "  $(GREEN)→ sshd: inactive$(RESET)\n"
	@echo ""
	@printf "  $(GREEN)✓ Locker stopped them again!$(RESET) As long as the device is\n"
	@printf "    disconnected, Locker keeps enforcing the lockdown.\n"
	@printf "    $(BOLD)Services cannot be started without the Android device.$(RESET)\n"
	$(PAUSE)

	@# ── Step 10: Reconnect the device (expect: active) ───────────
	$(call HEADER,"Step 10 — Reconnecting the device")
	@printf "  $(DIM)The authorized user plugs the Android device back in.$(RESET)\n"
	@printf "  $(DIM)(We re-create the connected serials file.)$(RESET)\n"
	$(call SUDO_CMD,bash -c 'echo '"'"'{"android_serial": "$(MOCK_SERIAL)"}'"'"' > $(SERIALS_FILE)')
	@printf "  $(GREEN)✓ Device reconnected.$(RESET)\n"
	@echo ""
	@printf "  $(YELLOW)Waiting for Locker to detect the reconnection...$(RESET)\n"
	@sleep 7
	@echo ""
	@printf "  $(TEAL)$$ locker list-services$(RESET)\n"
	@locker list-services
	@echo ""
	@printf "  $(TEAL)$$ systemctl is-active cron$(RESET)\n"
	@systemctl is-active cron && printf "  $(GREEN)→ cron: active$(RESET)\n" || printf "  $(RED)→ cron: inactive (unexpected!)$(RESET)\n"
	@printf "  $(TEAL)$$ systemctl is-active ssh$(RESET)\n"
	@systemctl is-active ssh && printf "  $(GREEN)→ ssh:  active$(RESET)\n" || printf "  $(RED)→ ssh:  inactive (unexpected!)$(RESET)\n"
	@printf "  $(TEAL)$$ systemctl is-active sshd$(RESET)\n"
	@systemctl is-active sshd && printf "  $(GREEN)→ sshd: active$(RESET)\n" || printf "  $(RED)→ sshd: inactive (unexpected!)$(RESET)\n"
	@echo ""
	@printf "  $(GREEN)✓ All services are back RUNNING. The device was recognized$(RESET)\n"
	@printf "  $(GREEN)  and Locker automatically unlocked the system.$(RESET)\n"
	$(PAUSE)

	@# ── Step 11: Show the audit log ──────────────────────────────
	$(call HEADER,"Step 11 — Audit log (last 30 lines)")
	@printf "  $(DIM)Every action — service starts, stops, device checks,$(RESET)\n"
	@printf "  $(DIM)CLI commands — is logged to /var/log/locker.log.$(RESET)\n"
	@echo ""
	@printf "  $(TEAL)$$ locker logs -n 30$(RESET)\n"
	@echo ""
	@locker logs -n 30
	$(PAUSE)

	@# ── Cleanup ──────────────────────────────────────────────────
	$(call HEADER,"Cleanup — Restoring safe state")
	$(call SUDO_CMD,locker set-mode permissive)
	@echo ""
	@printf "  $(DIM)Restarting cron, ssh, and sshd to leave the system healthy...$(RESET)\n"
	$(call SUDO_CMD,systemctl start cron)
	$(call SUDO_CMD,systemctl start ssh)
	$(call SUDO_CMD,systemctl start sshd)
	$(call SUDO_CMD,rm -f $(SERIALS_FILE))
	@echo ""
	@printf "  $(GREEN)✓ System restored to safe state.$(RESET)\n"
	@echo ""
	@printf "$(BOLD)$(TEAL)╔══════════════════════════════════════════════════════════════════════════════$(RESET)\n"
	@printf "$(BOLD)$(TEAL)║    					                                                      $(RESET)\n"
	@printf "$(BOLD)$(TEAL)║                    Demo Complete!  					                      $(RESET)\n"
	@printf "$(BOLD)$(TEAL)║                                                        	    		      $(RESET)\n"
	@printf "$(BOLD)$(TEAL)║$(RESET)   Locker continuously monitors your Android device and  	   		  $(RESET)\n"
	@printf "$(BOLD)$(TEAL)║$(RESET)   enforces service lockdowns in real time. No one can  	   		  $(RESET)\n"
	@printf "$(BOLD)$(TEAL)║$(RESET)   restart protected services without the physical device. 	    	  $(RESET)\n"
	@printf "$(BOLD)$(TEAL)║                                                                              $(RESET)\n"
	@printf "$(BOLD)$(TEAL)║$(RESET)   $(TEAL)locker add-service <name>$(RESET)    — protect a service    $(RESET)\n"
	@printf "$(BOLD)$(TEAL)║$(RESET)   $(TEAL)locker set-mode enforcing$(RESET)    — activate enforcement $(RESET)\n"
	@printf "$(BOLD)$(TEAL)║$(RESET)   $(TEAL)locker list-services$(RESET)         — see managed services $(RESET)\n"
	@printf "$(BOLD)$(TEAL)║$(RESET)   $(TEAL)locker logs -f$(RESET)               — follow the audit log $(RESET)\n"
	@printf "$(BOLD)$(TEAL)║                                                                              $(RESET)\n"
	@printf "$(BOLD)$(TEAL)╚══════════════════════════════════════════════════════════════════════════════$(RESET)\n"
	@echo ""
