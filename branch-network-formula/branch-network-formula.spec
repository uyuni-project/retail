#
# spec file for package branch-network-formula
#
# Copyright (c) 2025 SUSE LLC.
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


%define fname branch-network
%define fdir  %{_datadir}/susemanager/formulas
Name:           branch-network-formula
Version:        1.0.0
Release:        0
Summary:        Salt formula for configuring Branch Server network
License:        Apache-2.0
Group:          System/Packages
Url:            https://github.com/SUSE/salt-formulas
Source:         branch-network-formula-%{version}.tar.xz
BuildRoot:      %{_tmppath}/%{name}-%{version}-build
BuildArch:      noarch

%description
Salt pre-written state (formula) for managing configuration of Branch Server network.

%prep
%setup -q

%build

%install
mkdir -p %{buildroot}%{fdir}/states/{%{fname},_states,_modules}
mkdir -p %{buildroot}%{fdir}/metadata/%{fname}
cp -R branch-network/* %{buildroot}%{fdir}/states/%{fname}
cp -R metadata/* %{buildroot}%{fdir}/metadata/%{fname}
cp -R sysconfig/_states/* %{buildroot}%{fdir}/states/_states
cp -R sysconfig/_modules/* %{buildroot}%{fdir}/states/_modules

%files
%defattr(-,root,root)
%dir %{_datadir}/susemanager
%dir %{fdir}
%dir %{fdir}/states
%dir %{fdir}/states/_states
%dir %{fdir}/states/_modules
%dir %{fdir}/metadata
%{fdir}/states/%{fname}
%{fdir}/metadata/%{fname}
# sysconfig state and modules
%{fdir}/states/_states
%{fdir}/states/_modules

%changelog
