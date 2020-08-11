#
# spec file for package POS_Image-Graphical6
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

Name:           POS_Image-Graphical6
Version:        0.1
Release:        0
BuildRoot:      %{_tmppath}/%{name}-%{version}-build
Source:         POS_Image-Graphical6-%{version}.tar.xz
Summary:        SALT-based Graphical image
License:        GPL-2.0
Group:          System/Packages
BuildArch:      noarch
Requires:       kiwi-desc-saltboot
Requires:       image-server-tools
BuildRequires:  kiwi > 4.0

%description
Configuraton for SALT-based Graphical image.

%prep
%setup -q

%build

%install
mkdir -p %{buildroot}/usr/share/kiwi/image
cp -pR graphical-6.0.0 %{buildroot}/usr/share/kiwi/image

%files
%defattr(-,root,root,-)
/usr/share/kiwi/image

%changelog
