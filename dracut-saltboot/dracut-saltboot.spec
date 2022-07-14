#
# spec file for package dracut-saltboot
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

Name:           dracut-saltboot
Version:        0.1
Release:        0
BuildRoot:      %{_tmppath}/%{name}-%{version}-build
Source:         dracut-saltboot-%{version}.tar.xz
Summary:        SALT-based PXE network boot dracut module
License:        GPL-2.0
Group:          System/Packages
BuildArch:      noarch
BuildRequires:  dracut
Requires:       dracut

# Requires for saltboot functionality
Requires:       bind-utils
Requires:       cryptsetup
Requires:       curl
Requires:       device-mapper
Requires:       parted
Requires:       salt-minion
Recommends:     kiwi-tools

%description
dracut module for booting SALT-based PXE images.

%prep
%setup -q

%build

%install
mkdir -p %{buildroot}/usr/lib/dracut/modules.d/50saltboot
cp -R saltboot/* %{buildroot}/usr/lib/dracut/modules.d/50saltboot
chmod 755 %{buildroot}/usr/lib/dracut/modules.d/50saltboot/*

%files
%defattr(-,root,root,-)
/usr/lib/dracut/modules.d/50saltboot

%changelog
