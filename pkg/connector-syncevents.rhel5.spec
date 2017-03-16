%define module  @SHORT_NAME@

%define pyver 26
%define pybasever 2.6
%define __python /usr/bin/python%{pybasever}
%{!?python_sitelib: %define python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}
# Turn off the brp-python-bytecompile script
%define __os_install_post %(echo '%{__os_install_post}' | sed -e 's!/usr/lib[^[:space:]]*/brp-python-bytecompile[[:space:]].*$!!g')

Name:       vigilo-%{module}
Summary:    @SUMMARY@
Version:    @VERSION@
Release:    @RELEASE@%{?dist}
Source0:    %{name}-%{version}.tar.gz
URL:        @URL@
Group:      Applications/System
BuildRoot:  %{_tmppath}/%{name}-%{version}-%{release}-build
License:    GPLv2
Buildarch:  noarch

BuildRequires:   python26-distribute
BuildRequires:   python26-babel

Requires:   python26-distribute
Requires:   vigilo-common
Requires:   vigilo-connector
Requires:   vigilo-models

Requires(pre): shadow-utils


%description
@DESCRIPTION@
This application is part of the Vigilo Project <http://vigilo-project.org>


%prep
%setup -q

%build

%install
rm -rf $RPM_BUILD_ROOT
make install_pkg \
    DESTDIR=$RPM_BUILD_ROOT \
    PREFIX=%{_prefix} \
    SYSCONFDIR=%{_sysconfdir} \
    LOCALSTATEDIR=%{_localstatedir} \
    PYTHON=%{__python}

%find_lang %{name}


%pre
getent group vigilo-syncevents >/dev/null || groupadd -r vigilo-syncevents
getent passwd vigilo-syncevents >/dev/null || useradd -r -g vigilo-syncevents -d %{_sysconfdir}/vigilo/%{module} -s /sbin/nologin vigilo-syncevents
exit 0


%clean
rm -rf $RPM_BUILD_ROOT

%files -f %{name}.lang
%defattr(644,root,root,755)
%doc COPYING.txt
%attr(755,root,root) %{_bindir}/*
%dir %{_sysconfdir}/vigilo/
%dir %{_sysconfdir}/vigilo/%{module}
%attr(640,root,vigilo-syncevents) %config(noreplace) %{_sysconfdir}/vigilo/%{module}/settings.ini
%attr(644,root,root) %config(noreplace) %{_sysconfdir}/cron.d/*
%{python_sitelib}/vigilo*
%attr(-,vigilo-syncevents,vigilo-syncevents) %{_localstatedir}/lock/subsys/vigilo-connector-syncevents