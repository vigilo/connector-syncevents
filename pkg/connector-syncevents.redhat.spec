%define module  @SHORT_NAME@

%define pyver 26
%define pybasever 2.6
%define __python /usr/bin/python%{pybasever}
%define __os_install_post %{__python26_os_install_post}
%{!?python26_sitelib: %define python26_sitelib %(python26 -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}

Name:       vigilo-%{module}
Summary:    @SUMMARY@
Version:    @VERSION@
Release:    @RELEASE@%{?dist}
Source0:    %{name}-%{version}.tar.gz
URL:        @URL@
Group:      System/Servers
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
%{python26_sitelib}/vigilo*


%changelog
* Mon Feb 08 2010 Aurelien Bompard <aurelien.bompard@c-s.fr> - 1.0-1
- initial package
