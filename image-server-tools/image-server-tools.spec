#
# spec file for package image-server-tools
#
# Copyright (c) 2019 SUSE LINUX GmbH, Nuernberg, Germany.
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


Name:           image-server-tools
Version:        0.1
Release:        0
Summary:        Tools for building images for SUSE Manager Retail
License:        GPL-2.0
Group:          System/Packages
Source:         image-server-tools-%{version}.tar.xz
BuildRoot:      %{_tmppath}/%{name}-%{version}-build
BuildArch:      noarch

%description
Tools for building Kiwi images in SUSE Manager Retail environment

%prep
%setup -q

%build

%install
mkdir -p %{buildroot}/%{_bindir}
install -m 755 image-server-tools/suma-repos %{buildroot}/%{_bindir}

%files
%defattr(-,root,root,-)
%{_bindir}/*

%changelog
