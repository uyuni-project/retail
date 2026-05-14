# Thin wrapper around build.sh — delegates all logic there.
# SYNC: If you change this list, update PACKAGES in build.sh too
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

.PHONY: all test clean $(PACKAGES)

all test clean $(PACKAGES):
	@./build.sh $@
