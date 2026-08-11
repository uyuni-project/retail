#
# spec file for package kiwi-desc-saltboot
#
# Copyright (c) 2024 SUSE LLC.
#
# All modifications and additions to the file contributed by third parties
# remain the property of their copyright owners, unless otherwise agreed
# upon. The license for this file, and modifications and additions to the
# file, is the same license as for the pristine package itself (unless the
# license for the pristine package is not an Open Source License, in which
# case the license is the MIT License). An "Open Source License" is a
# license that conforms to the Open Source Definition (Version 1.9)
# published by the Open Source Initiative.

# Please submit bugfixes or comments via https://bugs.opensuse.org/
#

Name:           kiwi-desc-saltboot
Version:        0.1
Release:        0
BuildRoot:      %{_tmppath}/%{name}-%{version}-build
Source:         kiwi-desc-saltboot-%{version}.tar.bz2
Summary:        SALT-based PXE network boot template
License:        GPL-2.0
Group:          System/Packages
BuildArch:      noarch
%if 0%{?sle_version} >= 150100
BuildRequires:  python3-kiwi > 9.24
BuildRequires:  kiwi-boot-descriptions
Requires:       kiwi-boot-descriptions
%else
BuildRequires:  kiwi > 4.0
BuildRequires:  kiwi-desc-netboot
Requires:       kiwi-desc-netboot
%endif
Provides:       kiwi-boot:saltboot
Provides:       kiwi-image:cpio
Provides:       kiwi-image:pxe

%if 0%{?sle_version} >= 120000
ExclusiveArch:  x86_64 noarch
%else
ExclusiveArch:  i586 x86_64 noarch
%endif

%if 0%{?sle_version} >= 150100
%define kiwi_image_dir /usr/share/kiwi/custom_boot
%define linuxrc_include /usr/share/kiwi/custom_boot/functions.sh
%else
%define kiwi_image_dir /usr/share/kiwi/image
%define linuxrc_include /usr/share/kiwi/modules/KIWILinuxRC.sh
%endif

%description
kiwi boot (initrd) image for booting SALT-based PXE images.

%prep
%setup -q
ln -s %{linuxrc_include} saltboot/suse-SLES11/root/include
ln -s %{linuxrc_include} saltboot/suse-SLES12/root/include

%build

%install
mkdir -p %{buildroot}%{kiwi_image_dir}
cp -R saltboot %{buildroot}%{kiwi_image_dir}

%files
%defattr(-,root,root,-)
%{kiwi_image_dir}/saltboot

%changelog
