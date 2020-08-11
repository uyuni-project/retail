#
# spec file for package python-susemanager-retail
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

%if 0%{?suse_version} >= 1320
# SLE15
%define skip_python2 1
%define pythons python3
%else %if 0%{?suse_version} == 1315
# SLE12
%define skip_python3 1
%define pythons python2
%endif
%{?!python_module:%define python_module() python-%{**} python3-%{**}}

%define libname susemanager-retail

Name:           python-%{libname}
Version:        1.0
Release:        0
License:        GPL-2.0
Summary:        Python library for SUSE Manager for Retail automation
Url:            https://gitlab.suse.de/SLEPOS/SUMA_Retail
Group:          Development/Languages/Python
Source:         python-susemanager-retail-%{version}.tar.xz
BuildRequires:  %{python_module setuptools}
BuildRequires:  %{python_module rpm-macros}
BuildRequires:  unzip
BuildRequires:  fdupes
BuildArch:      noarch

%python_subpackages

%description
Python library implementing SUSE Manager for Retail bindings.

%package -n susemanager-retail-tools
Summary:    SUSE Manager for Retail command-line tools
Group:      Productivity/Networking/Other
Requires:   %{python_flavor}-%{libname} = %{version}
Requires:   xdelta3

%description -n susemanager-retail-tools
Command-line tools for managing a SUSE Manager for Retail environment.

retail_branch_init initializes and configures a Branch Server,
using data feed in from the command-line.

retail_yaml uses YAML structured data to initialize a Branch Server.
The script can also export the current configuration to a YAML file.

%prep
%setup -q -n %{name}-%{version}

%build
%python_build

%install
%python_install
%python_expand %fdupes %{buildroot}%{$python_sitelib}

%{python_expand mv %{buildroot}%{_bindir}/retail_branch_init %{buildroot}%{_bindir}/retail_branch_init-%$python_bin_suffix
mv %{buildroot}%{_bindir}/retail_yaml %{buildroot}%{_bindir}/retail_yaml-%$python_bin_suffix
mv %{buildroot}%{_bindir}/retail_migration %{buildroot}%{_bindir}/retail_migration-%$python_bin_suffix
mv %{buildroot}%{_bindir}/retail_create_delta %{buildroot}%{_bindir}/retail_create_delta-%$python_bin_suffix
ln -s %{_bindir}/retail_branch_init-%$python_bin_suffix %{buildroot}%{_bindir}/retail_branch_init
ln -s %{_bindir}/retail_yaml-%$python_bin_suffix %{buildroot}%{_bindir}/retail_yaml
ln -s %{_bindir}/retail_migration-%$python_bin_suffix %{buildroot}%{_bindir}/retail_migration
ln -s %{_bindir}/retail_create_delta-%$python_bin_suffix %{buildroot}%{_bindir}/retail_create_delta }

%files %{python_files}
%defattr(-,root,root)
%{python_sitelib}/*

%files -n susemanager-retail-tools
%defattr(-,root,root)
%doc example.yml
%{_bindir}/retail_branch_init-%{python_bin_suffix}
%{_bindir}/retail_yaml-%{python_bin_suffix}
%{_bindir}/retail_migration-%{python_bin_suffix}
%{_bindir}/retail_create_delta-%{python_bin_suffix}
%{_bindir}/retail_branch_init
%{_bindir}/retail_yaml
%{_bindir}/retail_migration
%{_bindir}/retail_create_delta

%changelog
