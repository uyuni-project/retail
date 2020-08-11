#
# spec file for package POS_Image-JeOS7
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

Name:           POS_Image-JeOS7
Version:        0.1
Release:        0
BuildRoot:      %{_tmppath}/%{name}-%{version}-build
Source:         POS_Image-JeOS7-%{version}.tar.xz
Summary:        SALT-based JeOS image
Url:            https://github.com/SUSE/manager-build-profiles/tree/master/OSImage
License:        GPL-2.0
Group:          System/Packages
BuildArch:      noarch
BuildRequires:  python3-kiwi

%description
Configuraton for SALT-based JeOS image.

%prep
%setup -q

%build

%install
mkdir -p %{buildroot}/usr/share/kiwi/image
cp -pR jeos-7.0.0 %{buildroot}/usr/share/kiwi/image

%files
%defattr(-,root,root,-)
%dir /usr/share/kiwi
/usr/share/kiwi/image

%changelog
