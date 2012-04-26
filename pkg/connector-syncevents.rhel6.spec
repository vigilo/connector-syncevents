%define module  @SHORT_NAME@

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

BuildRequires:   python-distribute
BuildRequires:   python-babel

Requires:   python-distribute
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
%attr(-,vigilo-syncevents,vigilo-syncevents) %{_localstatedir}/lock/vigilo-connector-syncevents


%changelog
* Fri Jan 21 2011 Vincent Quéméner <vincent.quemener@c-s.fr>
- Rebuild for RHEL6.

* Mon Feb 08 2010 Aurelien Bompard <aurelien.bompard@c-s.fr>
- initial package
