# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from ftplib import FTP
import StringIO
import hashlib
import tempfile

from django.core.files import File as DjangoFile

from lizard_efcis import tasks
from lizard_efcis.models import Activiteit
from lizard_efcis.models import ImportMapping
from lizard_efcis.models import ImportRun

DIR_IMPORTED_CORRECTLY = 'VERWERKT'
MAPPING_NAME = 'iBever-opnames'
IMPORT_USER = 'automatische ftp import'


def connect(ftp_location):
    """Return ftp connection."""
    ftp_connection = FTP(ftp_location.hostname)
    ftp_connection.login(ftp_location.username, ftp_location.password)
    if ftp_location.directory:
        ftp_connection.cwd(ftp_location.directory)
    return ftp_connection


def listdir(ftp_connection):
    return sorted(ftp_connection.nlst())


def importable_filenames(ftp_connection):
    # Idea: separate retryable_filenames for those with an attached error
    # report?
    filenames = listdir(ftp_connection)
    return [filename for filename in filenames
            if filename.startswith('iBever_')
            and filename.endswith('.txt')]


def django_file(ftp_connection, filename):
    """Return django File object, ready for feeding to FileField.

    See https://docs.djangoproject.com/en/1.8/topics/files/
    """
    # Make a local tempfile and copy/paste
    dont_care, tempfilename = tempfile.mkstemp(prefix='from_ftp_',
                                             suffix='.csv')
    ftp_connection.retrbinary('RETR %s' % filename,
                              open(tempfilename, 'wb').write)
    print(tempfilename)
    # Create a django file, ready for feeding to a filefield
    return DjangoFile(open(tempfilename, 'rb'))


def write_file(ftp_connection, filename, contents):
    file_like = StringIO.StringIO()
    file_like.write(contents)
    file_like.seek(0)  # "Wind back" so that read() works.
    ftp_connection.storbinary('STOR %s' % filename, file_like)


def delete_file(ftp_connection, filename):
    """Delete file. Return success message if succesful."""
    return ftp_connection.delete(filename)


def move_file(ftp_connection, filename1, filename2):
    """Move file. Filename can contain *relative* path."""
    ftp_connection.rename(filename1, filename2)


def debug_info(ftp_location):
    """Return string with information about the FTP connection."""
    output = []
    output.append("Looking at %s" % ftp_location)
    ftp_connection = connect(ftp_location)
    output.append("Directory contents:")
    for filename in listdir(ftp_connection):
        output.append("    - %s" % filename)
    output.append("Importable csv files:")
    for filename in importable_filenames(ftp_connection):
        output.append("    - %s" % filename)
    output.append("Attempting to write file...")
    filename = 'ftp_test_file'
    write_file(ftp_connection,
               filename,
               "Write/move/read test successful")
    output.append("Attempting to move file...")
    filename_in_subdir = '%s/%s' % (DIR_IMPORTED_CORRECTLY, filename)
    move_file(ftp_connection,
              filename,
              filename_in_subdir)
    output.append(django_file(ftp_connection, filename_in_subdir).read())
    output.append("Attempting to delete file...")
    output.append(delete_file(ftp_connection, filename_in_subdir))
    return '\n'.join(output)


def handle_first_file(ftp_location):
    output = []
    output.append("Looking at %s" % ftp_location)
    ftp_connection = connect(ftp_location)
    filenames = importable_filenames(ftp_connection)
    if not filenames:
        output.append("Nothing to import")
        return '\n'.join(output)

    import_activity, created1 = Activiteit.objects.get_or_create(
        activiteit="Automatische FTP import")
    filename = filenames[0]
    import_run, created2 = ImportRun.objects.get_or_create(
        activiteit=import_activity,
        name=filename)
    if created2:
        output.append("Nieuwe import run aangemaakt: %s" % import_run)
    else:
        output.append("Bestaande import run gebruikt: %s" % import_run)

    import_mapping = ImportMapping.objects.get(code=MAPPING_NAME)
    import_run.import_mapping = import_mapping
    import_run.save()

    new_attachment = django_file(ftp_connection, filename)
    replace_attachment = False
    if import_run.attachment:
        old_md5_hash = hashlib.md5(import_run.attachment.read()).hexdigest()
        new_md5_hash = hashlib.md5(new_attachment.read()).hexdigest()
        if old_md5_hash == new_md5_hash:
            output.append("Attachment is niet gewijzigd.")
        else:
            output.append(
                "Bestand op de ftp is anders dan het huidige attachment.")
            replace_attachment = True

    if replace_attachment or not import_run.attachment:
        import_run.attachment = new_attachment
        import_run.validated = False
        import_run.imported = False
        import_run.save()
        output.append("CSV van ftp als nieuw import run attachment toegevoegd.")

    if not import_run.validated:
        output.append("Import run is nog niet gecontroleerd, dat proberen we nu...")
        tasks.check_file(IMPORT_USER, import_run=import_run)
    import_run = ImportRun.objects.get(id=import_run.id)  # Reload

    if import_run.validated and not import_run.imported:
        output.append("Import run is nog niet geimporteerd, dat proberen we nu...")
        tasks.import_data(IMPORT_USER, import_run=import_run)
    import_run = ImportRun.objects.get(id=import_run.id)  # Reload

    log_filename = 'efcis_importlog_' + filename
    if import_run.action_log:
        output.append("Dit is de log van het controleren/importeren:")
        output.append(import_run.action_log_for_logfile())
        write_file(ftp_connection,
                   log_filename,
                   import_run.action_log_for_logfile())
        output.append("(Logfile is als %s naar de ftp geschreven)" % log_filename)

    if import_run.imported:
        success_filename = '%s/%s' % (DIR_IMPORTED_CORRECTLY, filename)
        output.append("Import is gelukt. Op de ftp verplaatsen we %s naar %s..." % (
            filename, success_filename))
        move_file(ftp_connection,
                  filename,
                  success_filename)
        output.append("Logfile %s is niet meer nodig. We verwijderen het..." % (
            log_filename))
        delete_file(log_filename)

    return '\n'.join(output)