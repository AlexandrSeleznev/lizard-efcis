from optparse import make_option
import os

from django.conf import settings
from django.core.management.base import BaseCommand

from lizard_efcis.import_data import DataImport
from lizard_efcis.models import Activiteit, ImportMapping


class Command(BaseCommand):
    help = '''Import data volgens de mapping.'''

    option_list = BaseCommand.option_list + (
        make_option('--mapping',
                    default=None,
                    help='mapping code'),
    )

    def handle(self, *args, **options):
        self.stdout.write('Start import')
        mapping_code = options.get('mapping', None)
        if not mapping_code:
            self.stdout.write('Geef een mapping code.')
            return
        if not ImportMapping.objects.filter(code=mapping_code).exists():
            self.stdout.write(
                'De mapping code {} is niet gevonden.'.format(mapping_code))
            return
        data_import = DataImport()
        data_import.data_dir = os.path.join(
            settings.DATA_IMPORT_DIR, 'hdsr', 'historisch')

        activiteiten = Activiteit.objects.filter(activiteit='import ibever')
        if activiteiten.exists():
            activiteit = activiteiten[0]
        else:
            activiteit = Activiteit(activiteit='import ibever')
            activiteit.save()

        data_import.import_csv('ibever.csv', mapping_code, activiteit)

        self.stdout.write('Einde import')
