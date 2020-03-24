#
# spec file for package kiwi-desc-saltboot
#
# Copyright (c) 2020 SUSE LLC.
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
BuildRequires:  kiwi > 4.0
BuildRequires:  kiwi-desc-netboot
Requires:       kiwi-desc-netboot
Provides:       kiwi-boot:saltboot
Provides:       kiwi-image:cpio
Provides:       kiwi-image:pxe

%if 0%{?sle_version} >= 120000
ExclusiveArch:  x86_64 noarch
%else
ExclusiveArch:  i586 x86_64 noarch
%endif

%description
kiwi boot (initrd) image for booting SALT-based PXE images.

%prep
%setup -q

%build

%install
mkdir -p %{buildroot}/usr/share/kiwi/image
cp -R saltboot %{buildroot}/usr/share/kiwi/image

%files
%defattr(-,root,root,-)
/usr/share/kiwi/image

%changelog
