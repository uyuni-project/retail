#
# spec file for package image-sync-formula
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


%define fname image-synchronize
%define fdir  %{_datadir}/susemanager/formulas
Name:           image-sync-formula
Version:        0.1
Release:        0
Summary:        Salt formula for syncing images to Branch Server
License:        GPL-2.0
Group:          System/Packages
Source:         image-sync-formula-%{version}.tar.xz
BuildRoot:      %{_tmppath}/%{name}-%{version}-build
BuildArch:      noarch

%description
Salt formula for syncing images to Branch Server.

%prep
%setup -q

%build

%install
mkdir -p %{buildroot}%{fdir}/states/%{fname}
mkdir -p %{buildroot}%{fdir}/metadata/%{fname}
cp -R %{fname}/* %{buildroot}%{fdir}/states/%{fname}
# keep compatibility:
cp -R image-sync.sls %{buildroot}%{fdir}/states
cp -R metadata/* %{buildroot}%{fdir}/metadata/%{fname}
cp -R _states _modules %{buildroot}%{fdir}/states/

%files
%defattr(-,root,root)
%dir %{_datadir}/susemanager
%dir %{fdir}
%dir %{fdir}/states
%dir %{fdir}/metadata
%{fdir}/states/%{fname}
%{fdir}/states/image-sync.sls
%{fdir}/metadata/%{fname}
%{fdir}/states/_states
%{fdir}/states/_modules

%changelog
