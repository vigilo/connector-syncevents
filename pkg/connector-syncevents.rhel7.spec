%define module  @SHORT_NAME@

Name:       vigilo-%{module}
Summary:    @SUMMARY@
Version:    @VERSION@
Release:    @RELEASE@%{?dist}
Source0:    %{name}-%{version}@PREVERSION@.tar.gz
URL:        @URL@
Group:      Applications/System
BuildRoot:  %{_tmppath}/%{name}-%{version}-%{release}-build
License:    GPLv2
Buildarch:  noarch

BuildRequires:   python-babel



Requires:   vigilo-common
Requires:   vigilo-connector
Requires:   vigilo-models

Requires(pre): shadow-utils


%description
@DESCRIPTION@
This application is part of the Vigilo Project <https://www.vigilo-nms.com>


%prep
%setup -q -n %{name}-%{version}@PREVERSION@

%build

%install
rm -rf $RPM_BUILD_ROOT
make install_pkg \
    DESTDIR=$RPM_BUILD_ROOT \
    PREFIX=%{_prefix} \
    SYSCONFDIR=%{_sysconfdir} \
    LOCALSTATEDIR=%{_localstatedir} \
    PYTHON=%{__python}
mkdir -p $RPM_BUILD_ROOT/%{_tmpfilesdir}
install -m 644 pkg/%{name}.conf $RPM_BUILD_ROOT/%{_tmpfilesdir}

%find_lang %{name}


%pre
getent group vigilo-syncevents >/dev/null || groupadd -r vigilo-syncevents
getent passwd vigilo-syncevents >/dev/null || useradd -r -g vigilo-syncevents -d %{_sysconfdir}/vigilo/%{module} -s /sbin/nologin vigilo-syncevents
exit 0

%post
%tmpfiles_create %{_tmpfilesdir}/%{name}.conf

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
%attr(644,root,root) %{_tmpfilesdir}/%{name}.conf

%changelog
* Fri Mar 17 2017 Yves Ouattara <yves.ouattara@c-s.fr>
- Rebuild for RHEL7.

* Fri Jan 21 2011 Vincent Quéméner <vincent.quemener@c-s.fr>
- Rebuild for RHEL6.

* Mon Feb 08 2010 Aurelien Bompard <aurelien.bompard@c-s.fr>
- initial package
