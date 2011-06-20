import commonware
import tempfile
import os

from test_utils import TestCase

from nose.tools import eq_

from django.contrib.auth.models import User
from django.conf import settings

from jetpack.models import Package, PackageRevision, Module, Attachment, SDK
from jetpack.errors import SelfDependencyException, FilenameExistException, \
        DependencyException
from base.templatetags.base_helpers import hashtag

log = commonware.log.getLogger('f.test')


class PackageRevisionTest(TestCase):
    fixtures = ['mozilla_user', 'users', 'core_sdk', 'packages']

    def setUp(self):
        self.author = User.objects.get(username='john')
        self.addon = self.author.packages_originated.addons()[0:1].get()
        self.library = self.author.packages_originated.libraries()[0:1].get()
        self.hashtag = hashtag()
        self.xpi_file = os.path.join(settings.XPI_TARGETDIR,
                "%s.xpi" % self.hashtag)

    def tearDown(self):
        if os.path.exists(self.xpi_file):
            os.remove(self.xpi_file)

    def test_first_revision_creation(self):
        addon = Package(author=self.author, type='a')
        addon.save()
        revisions = PackageRevision.objects.filter(package__pk=addon.pk)
        eq_(1, revisions.count())
        revision = revisions[0]
        eq_(revision.full_name, addon.full_name)
        eq_(revision.name, addon.name)
        eq_(revision.author.username, addon.author.username)
        eq_(revision.revision_number, 0)
        eq_(revision.pk, addon.latest.pk)
        eq_(revision.pk, addon.version.pk)
        eq_(revision.name, addon.name)

    def test_name_change(self):
        addon = Package(author=self.author, type='a')
        addon.save()
        revisionA = PackageRevision.objects.filter(package__pk=addon.pk)[0]
        addon.latest.set_full_name("TEST NAME CHANGE")
        addon.save()
        addon.latest.save()
        revisionB = PackageRevision.objects.filter(package__pk=addon.pk)[0]
        log.debug(revisionB.name)
        log.debug(addon.name)
        eq_(revisionB.name, addon.name)
        assert revisionA.pk != revisionB.pk
        assert revisionA.name != revisionB.name
        eq_(len(addon.revisions.all()), 2)

    def test_save(self):
        # system should create new revision on save
        addon = Package(author=self.author, type='a')
        addon.save()
        revisions = PackageRevision.objects.filter(package__name=addon.name)
        first = revisions[0]
        first.save()
        revisions = PackageRevision.objects.filter(package__name=addon.name)
        eq_(2, revisions.count())

        # first is not the same package anymore and it does not have
        # the version_name parameter
        eq_(None, first.version_name)

        # "old" addon doesn't know about the changes
        self.assertNotEqual(addon.latest.revision_number,
                            first.revision_number)

        # reloading addon to update changes
        addon = first.package

        # first is the latest
        eq_(addon.latest.revision_number,
                         first.revision_number)
        self.assertNotEqual(addon.version.revision_number,
                            addon.latest.revision_number)

    def test_set_version(self):
        addon = Package(author=self.author, type='a')
        addon.save()
        first = addon.latest
        old_id = first.id
        first.set_version('test')

        # setting version does not make new revision
        eq_(first.id, old_id)

        # setting version sets it for revision, package
        # and assigns revision to package
        eq_(first.version_name, 'test')
        eq_(first.package.version_name, 'test')
        eq_(first.package.version.pk, first.pk)

    def test_adding_and_removing_dependency(self):
        revisions = PackageRevision.objects.filter(package__pk=self.addon.pk)
        count = revisions.count()
        first = revisions[0]
        lib = PackageRevision.objects.filter(package__pk=self.library.pk)[0]

        # first depends on lib
        first.dependency_add(lib)
        revisions = PackageRevision.objects.filter(package__pk=self.addon.pk)

        # revisions number increased
        eq_(count + 1, revisions.count())

        first = revisions[1]
        second = revisions[0]

        # only the second revision has the dependencies
        eq_(0, first.dependencies.count())
        eq_(1, second.dependencies.count())

        # remove the dependency
        second.dependency_remove(lib)

        revisions = PackageRevision.objects.filter(package__pk=self.addon.pk)
        first = revisions[2]
        second = revisions[1]
        third = revisions[0]

        # only the second revision has the dependencies
        eq_(0, first.dependencies.count())
        eq_(1, second.dependencies.count())
        eq_(0, third.dependencies.count())

    def test_save_with_dependency(self):
        # system should copy on save with all dependencies
        revisions = PackageRevision.objects.filter(package__pk=self.addon.pk)
        first = revisions[0]
        lib = PackageRevision.objects.filter(package__pk=self.library.pk)[0]

        # make first depends on lib
        # it's setting dependency in django standard way, to keep
        # revision structure
        first.dependencies.add(lib)

        # save creates a new revision
        first.save()
        revisions = PackageRevision.objects.filter(package__pk=self.addon.pk)
        first = revisions[1]
        second = revisions[0]
        # both revisions have the same dependencies
        eq_(first.dependencies.count(),
                         second.dependencies.count())
        eq_(first.dependencies.all()[0].pk, lib.pk)
        eq_(second.dependencies.all()[0].pk, lib.pk)

    def test_adding_addon_as_dependency(self):
        " Add-on can't be a dependency "
        lib = PackageRevision.objects.filter(package__pk=self.library.pk)[0]
        addon = PackageRevision.objects.filter(package__pk=self.addon.pk)[0]
        self.assertRaises(TypeError, lib.dependency_add, addon)
        eq_(0, lib.dependencies.all().count())

    def test_adding_library_twice(self):
        " Check recurrent dependency (one level deep) "
        lib = self.library.latest
        addon = self.addon.latest
        addon.dependency_add(lib)
        self.assertRaises(DependencyException, addon.dependency_add, lib)


    def test_adding_library_naming_conflict(self):
        " Check recurrent dependency (all levels) "
        john_lib = self.library
        john_lib2 = Package(author=self.author, type='l')
        john_lib2.save()

        jan = User.objects.get(username='jan')
        jan_lib = Package(author=jan, type='l')
        jan_lib.save()
        jan_conflict = Package(author=jan, type='l', full_name=john_lib.full_name)
        jan_conflict.save()

        john_lib.latest.dependency_add(jan_lib.latest)

        addon = self.addon.latest
        addon.dependency_add(john_lib.latest)
        addon.dependency_add(jan_lib.latest)

        self.assertRaises(DependencyException, addon.dependency_add, jan_conflict.latest)


        john_lib2.latest.dependency_add(jan_conflict.latest)
        self.assertRaises(DependencyException, addon.dependency_add, john_lib2.latest)

    def test_adding_library_self(self):
        " Check recurrent dependency (one level only) "
        lib = self.library.latest
        self.assertRaises(SelfDependencyException, lib.dependency_add, lib)

    def test_removing_not_existing_dependency(self):
        " Removing not existing dependency should raise an error "
        self.assertRaises(DependencyException,
                          self.addon.latest.dependency_remove_by_id_number,
                          self.library.id_number)
        self.assertRaises(DependencyException,
                         self.addon.latest.dependency_remove,
                         self.library.latest)

    def test_adding_module(self):
        " Test if module is added properly "
        addon = Package(author=self.author, type='a')
        addon.save()
        first = addon.latest
        # add module
        first.module_create(
            filename='test',
            author=self.author
        )

        " module should be added to the latter only "
        revisions = addon.revisions.all()
        first = revisions[1]
        second = revisions[0]

        # all add-ons have a default modules created
        eq_(1, first.modules.count())
        eq_(2, second.modules.count())

    def test_adding_attachment(self):
        " Test if attachment is added properly "
        addon = Package(author=self.author, type='a')
        addon.save()
        first = addon.latest
        first.attachment_create(
            filename='test.txt',
            author=self.author
        )

        " module should be added to the latter revision only "
        revisions = addon.revisions.all()
        first = revisions[1]
        second = revisions[0]

        eq_(0, first.attachments.count())
        eq_(1, second.attachments.count())

    def test_read_write_attachment(self):
        """Test that we can read and write to an attachment."""
        addon = Package(author=self.author, type='a')
        addon.save()
        first = addon.latest
        filename = tempfile.mkstemp()[1]
        try:
            attachment = first.attachment_create(
                filename='test',
                ext='txt',
                author=self.author
            )
            attachment.data = 'This is a test.'
            attachment.write()
            assert attachment.read() == attachment.data
            assert not attachment.changed()
        finally:
            os.remove(filename)

    def test_updating_module(self):
        " Updating module has some additional action "
        addon = Package(author=self.author, type='a')
        addon.save()
        first = addon.latest
        mod = first.module_create(
            filename='test_filename',
            author=self.author
        )
        mod.code = 'test'
        first.update(mod)

        # create new revision on module update
        eq_(3, addon.revisions.count())
        eq_(2, Module.objects.filter(
            filename='test_filename').count())

        first = addon.revisions.all()[1]
        last = addon.revisions.all()[0]

        eq_(2, last.modules.count())

    def test_adding_module_with_existing_filename(self):
        " filename is unique in package "
        first = PackageRevision.objects.filter(package__pk=self.addon.pk)[0]
        first.module_create(
            filename='test_filename',
            author=self.author
        )
        # Exception on creating the module from PackageRevision
        self.assertRaises(FilenameExistException, first.module_create,
            **{'filename': 'test_filename', 'author': self.author}
        )
        # Exception on adding a different module with the same filename
        mod = Module.objects.create(
            filename='test_filename',
            author=self.author
        )
        self.assertRaises(FilenameExistException, first.module_add, mod)

    def test_adding_attachment_with_existing_filename(self):
        """Filename is unique per packagerevision."""
        first = PackageRevision.objects.filter(package__pk=self.addon.pk)[0]
        first.attachment_create(
            filename='test_filename',
            ext='txt',
            author=self.author
        )
        self.assertRaises(FilenameExistException, first.attachment_create,
            **{'filename': 'test_filename',
               'ext': 'txt',
               'author': self.author}
        )
        att = Attachment.objects.create(
            filename='test_filename',
            ext='txt',
            author=self.author
        )
        self.assertRaises(FilenameExistException, first.attachment_add, att)

    def test_force_sdk(self):
        addon = Package.objects.create(
            full_name="Other Package",
            author=self.author,
            type='a')
        oldsdk = addon.latest.sdk

        mozuser = User.objects.get(username='mozilla')
        version='testsdk'
        kit_lib = PackageRevision.objects.create(
                author=mozuser,
                package=oldsdk.kit_lib.package,
                revision_number=oldsdk.kit_lib.revision_number + 1,
                version_name=version)
        core_lib = PackageRevision.objects.create(
                author=mozuser,
                package=oldsdk.core_lib.package,
                revision_number=oldsdk.core_lib.revision_number + 1,
                version_name=version)
        sdk = SDK.objects.create(
                version=version,
                kit_lib=kit_lib,
                core_lib=core_lib,
                dir='somefakedir')

        addon.latest.force_sdk(sdk)
        eq_(len(addon.revisions.all()), 1)
        eq_(addon.latest.sdk.version, version)
        eq_(addon.latest.commit_message,
                'Automatic Add-on SDK upgrade to version (%s)' % sdk.version)
        addon.latest.force_sdk(oldsdk)
        eq_(len(addon.revisions.all()), 1)
        eq_(addon.latest.commit_message.count('SDK'), 2)

    """
    Althought not supported on view and front-end,
    there is no harm in these two

    def test_adding_module_which_was_added_to_other_package_before(self):
        " ""
        system should prevent from adding a module to more than one packages
        " ""
        addon = Package.objects.create(
            full_name="Other Package",
            author=self.author,
            type='a'
        )
        rev = addon.latest
        first = PackageRevision.objects.filter(package__pk=self.addon.pk)[0]
        mod = Module.objects.create(
            filename='test_filename',
            author=self.author
        )
        first.module_add(mod)
        self.assertRaises(AddingModuleDenied, rev.module_add, mod)

    def test_adding_attachment_which_was_added_to_other_package_before(self):
        " assigning attachment to more than one packages should be prevented! "
        addon = Package.objects.create(
            full_name="Other Package",
            author=self.author,
            type='a'
        )
        rev = addon.latest
        first = PackageRevision.objects.filter(package__pk=self.addon.pk)[0]
        att = Attachment.objects.create(
            filename='test_filename',
            ext='.txt',
            path='/tmp/upload_path',
            author=self.author
        )
        first.attachment_add(att)
        self.assertRaises(AddingAttachmentDenied, rev.attachment_add, att)
    """

