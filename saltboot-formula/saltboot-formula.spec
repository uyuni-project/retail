#
# spec file for package saltboot-formula
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

Name:           saltboot-formula
Version:        0.1
Release:        0
BuildRoot:      %{_tmppath}/%{name}-%{version}-build
Source:         saltboot-formula-%{version}.tar.xz
Summary:        Formula for boot image of POS terminal
License:        GPL-2.0
Group:          System/Packages
BuildArch:      noarch
Requires:       salt-master
Requires:       susemanager-sls
BuildRequires:  salt-master
BuildRequires:  susemanager-sls
%define fname saltboot

%description
Formula for boot image of POS terminal.

%prep
%setup -q

%build

%install
mkdir -p %{buildroot}/usr/share/susemanager/formulas/states/{%{fname},%{fname}-reactor,_states}
mkdir -p %{buildroot}/usr/share/susemanager/formulas/metadata/%{fname}
mkdir -p %{buildroot}/usr/share/susemanager/formulas/metadata/%{fname}-group
cp -R %{fname}/* %{buildroot}/usr/share/susemanager/formulas/states/%{fname}
cp -R _states/* %{buildroot}/usr/share/susemanager/formulas/states/_states
cp -R %{fname}-reactor/* %{buildroot}/usr/share/susemanager/formulas/states/%{fname}-reactor
cp metadata/form.yml %{buildroot}/usr/share/susemanager/formulas/metadata/%{fname}
cp metadata/metadata.yml %{buildroot}/usr/share/susemanager/formulas/metadata/%{fname}
cp metadata/*.example %{buildroot}/usr/share/susemanager/formulas/metadata/%{fname}
cp metadata/%{fname}-group-form.yml %{buildroot}/usr/share/susemanager/formulas/metadata/%{fname}-group/form.yml
cp metadata/%{fname}-group-metadata.yml %{buildroot}/usr/share/susemanager/formulas/metadata/%{fname}-group/metadata.yml

mkdir -p %{buildroot}/etc/salt/master.d
cp -R master.d/* %{buildroot}/etc/salt/master.d


%files
%defattr(-,root,root,-)
/usr/share/susemanager/formulas/states/%{fname}
/usr/share/susemanager/formulas/states/%{fname}-reactor
/usr/share/susemanager/formulas/states/_states
/usr/share/susemanager/formulas/metadata/%{fname}
/usr/share/susemanager/formulas/metadata/%{fname}-group
/etc/salt/master.d/saltboot.conf

%changelog
