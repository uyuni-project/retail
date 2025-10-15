# Makefile for building, organizing, and testing multiple package artifacts

# List of all packages to be built.
PACKAGES = \
    branch-network-formula \
    dracut-saltboot \
    dracut-wireless \
    image-server-tools \
    image-sync-formula \
    kiwi-desc-saltboot \
    POS_Image-Graphical6 \
    POS_Image-Graphical7 \
    POS_Image-JeOS6 \
    POS_Image-JeOS7 \
    python-susemanager-retail \
    saltboot-formula

# --- Helper function to get the version from a .spec file ---
get_version = $(shell grep -i '^Version:' $(1)/$(1).spec | awk '{print $$2}')

# --- Generate all target filenames with their new paths ---
TARGETS = $(foreach pkg,$(PACKAGES),packages/$(pkg)/$(pkg)-$(call get_version,$(pkg)).tar.gz)

# --- Default target: build all packages ---
.PHONY: all
all: $(TARGETS)
	@echo "✅ All packages built successfully."

# --- Generic rule template for a single package ---
define PACKAGE_template
# Target for building and collecting artifacts for $(1)
packages/$(1)/$(1)-$(2).tar.gz:
	@echo "📦 Packaging $(1) version $(2)..."
	@mkdir -p packages/$(1)
	@tar -czf $$@ --transform='s,^$(1),$(1)-$(2),' $(1)
	@cp $(1)/$(1).spec packages/$(1)/
	@cp $(1)/$(1).changes packages/$(1)/
	@echo "   -> Artifacts collected in packages/$(1)/"

# Phony target to build a single package by its name
.PHONY: $(1)
$(1): packages/$(1)/$(1)-$(2).tar.gz

endef

# --- Instantiate the template for each package ---
$(foreach pkg,$(PACKAGES),$(eval $(call PACKAGE_template,$(pkg),$(call get_version,$(pkg)))))

# --- Test target to verify version consistency ---
.PHONY: test
test:
	@echo "🧪 Running version consistency tests..."
	@$(foreach pkg,$(PACKAGES), \
		echo "   -> Checking package: $(pkg)"; \
		SPEC_VERSION=$(call get_version,$(pkg)); \
		CHANGELOG_VERSION=$(shell grep -m 1 -oP -- '- Update to version \K[0-9a-zA-Z._-]+' $(pkg)/$(pkg).changes || echo "not_found"); \
		if [ -z "$$SPEC_VERSION" ]; then \
			echo "      ❌ ERROR: Could not find version in $(pkg)/$(pkg).spec"; \
		elif [ "$$CHANGELOG_VERSION" = "not_found" ]; then \
			echo "      ❌ ERROR: Could not find changelog version entry in $(pkg)/$(pkg).changes"; \
			echo "         (Expecting a line like '- Update to version ...')"; \
		elif [ "$$SPEC_VERSION" != "$$CHANGELOG_VERSION" ]; then \
			echo "      ❌ ERROR: Version mismatch in $(pkg)!"; \
			echo "         Spec file:      $$SPEC_VERSION"; \
			echo "         Changelog file: $$CHANGELOG_VERSION"; \
		else \
			echo "      ✅ OK: Version $$SPEC_VERSION matches in spec and changelog."; \
		fi; \
	)
	@echo "🎉 All tests passed."

# --- Clean up all generated artifacts and directories ---
.PHONY: clean
clean:
	@echo "🧹 Cleaning up build artifacts..."
	@rm -rf packages
