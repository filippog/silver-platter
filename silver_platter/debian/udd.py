#!/usr/bin/python
# Copyright (C) 2018 Jelmer Vernooij <jelmer@jelmer.uk>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

"""Wrapper around the vcswatch table in UDD."""

from __future__ import absolute_import

from email.utils import parseaddr
import psycopg2

import distro_info


class PackageData(object):

    def __init__(self, name, vcs_url, maintainer_email, uploader_emails):
        self.name = name
        self.vcs_url = vcs_url
        self.maintainer_email = maintainer_email
        self.uploader_emails = uploader_emails


def connect_udd_mirror():
    """Connect to the public UDD mirror."""
    conn = psycopg2.connect(
        database="udd",
        user="udd-mirror",
        password="udd-mirror",
        port=5432,
        host="udd-mirror.debian.net")
    conn.set_client_encoding('UTF8')
    return conn


def extract_uploader_emails(uploaders):
    return ([parseaddr(p)[0] for p in uploaders.split(',')]
            if uploaders else [])


class UDD(object):

    @classmethod
    def public_udd_mirror(cls):
        return cls(connect_udd_mirror())

    def __init__(self, conn):
        self._conn = conn

    def get_source_package(self, name):
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT source, vcs_type, vcs_url, maintainer_email, uploaders "
            "FROM sources WHERE source = %s order by version desc", (name, ))
        row = cursor.fetchone()
        uploader_emails = extract_uploader_emails(row[4])
        return PackageData(
                name=row[0], vcs_url=row[2],
                maintainer_email=row[3],
                uploader_emails=uploader_emails)

    def iter_ubuntu_source_packages(self, packages=None):
        release = distro_info.UbuntuDistroInfo().devel()
        cursor = self._conn.cursor()
        cursor.execute("""\
            select distinct source, vcs_type, vcs_url, maintainer_email, uploaders FROM ubuntu_sources WHERE vcs_type != '' AND release = %s""" + (" AND source IN %s" if packages is not None else ""), ((release, ) + ((tuple(packages),) if packages is not None else ())))
        row = cursor.fetchone()
        while row:
            uploader_emails = extract_uploader_emails(row[4])
            yield PackageData(
                name=row[0], vcs_url=row[2],
                maintainer_email=row[3],
                uploader_emails=uploader_emails)
            row = cursor.fetchone()

    def iter_source_packages_by_lintian(self, tags, packages=None):
        """Iterate over all of the packages affected by a set of tags."""
        package_rows = {}
        package_tags = {}
        cursor = self._conn.cursor()
        def process(cursor):
            row = cursor.fetchone()
            while row:
                package_rows[row[0]] = row[:5]
                package_tags.setdefault(row[0], []).append(row[5])
                row = cursor.fetchone()
        cursor.execute("""\
            select distinct sources.source, sources.vcs_type, sources.vcs_url, sources.maintainer_email, sources.uploaders, lintian.tag from lintian full outer join sources on sources.source = lintian.package and sources.version = lintian.package_version and sources.release = 'sid' where tag in %s and package_type = 'source' and vcs_type != ''""" + (" AND sources.source IN %s" if packages is not None else ""), (tuple(tags), ) + ((tuple(packages),) if packages is not None else ()))
        process(cursor)
        cursor.execute("""\
select distinct sources.source, sources.vcs_type, sources.vcs_url, sources.maintainer_email, sources.uploaders, lintian.tag from lintian inner join packages on packages.package = lintian.package and packages.version = lintian.package_version inner join sources on sources.version = packages.version and sources.source = packages.source and sources.release = 'sid' where lintian.tag in %s and lintian.package_type = 'binary' and vcs_type != ''""" + (" AND sources.source IN %s" if packages is not None else ""), (tuple(tags), ) + ((tuple(packages),) if packages is not None else ()))
        process(cursor)
        for row in package_rows.values():
            uploader_emails = extract_uploader_emails(row[4])
            yield PackageData(
                name=row[0], vcs_url=row[2], maintainer_email=row[3],
                uploader_emails=uploader_emails), package_tags[row[0]]