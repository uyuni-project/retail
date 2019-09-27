#!/bin/sh
test -f /.kconfig && . /.kconfig
test -f /.profile && . /.profile

echo "Configure image: [$kiwi_iname]..."

#==========================================
# setup build day
#------------------------------------------
baseSetupBuildDay

#==========================================
# remove unneded kernel files
#------------------------------------------
suseStripKernel

#==========================================
# Setup ttf font for plymouth label-ft module
#------------------------------------------
font=$(fc-match -f %{file})
echo "Using font $font"
cp "$font" $INITRDDIR/usr/share/fonts/Plymouth.ttf
rm -rf /usr/share/fonts/truetype
#
# this has broken deps anyway
rm /usr/lib64/plymouth/label.so
#==========================================
# remove unneeded files
#------------------------------------------
suseStripInitrd
find / -name '*.py[co]' -delete

#==========================================
# umount
#------------------------------------------
umount /proc >/dev/null 2>&1

exit 0
