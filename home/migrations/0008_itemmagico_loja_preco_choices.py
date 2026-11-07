from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0007_tbmagia_spells'),
    ]

    operations = [
        migrations.AddField(
            model_name='tbitemmagico',
            name='loja',
            field=models.CharField(blank=True, db_column='Loja', help_text='Loja/caravana em que o item pode aparecer.', max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='tbitemmagico',
            name='preco',
            field=models.DecimalField(blank=True, db_column='Preco', decimal_places=2, help_text='Preco em PO.', max_digits=12, null=True),
        ),
        migrations.AlterField(
            model_name='tbitemmagico',
            name='raridade',
            field=models.CharField(choices=[('comum', 'Comum'), ('comum_menor', 'Comum Menor'), ('comum_maior', 'Comum Maior'), ('incomum', 'Incomum'), ('incomum_menor', 'Incomum Menor'), ('incomum_maior', 'Incomum Maior'), ('raro', 'Raro'), ('raro_menor', 'Raro Menor'), ('raro_maior', 'Raro Maior'), ('muito_raro', 'Muito Raro'), ('muito_raro_menor', 'Muito Raro Menor'), ('muito_raro_maior', 'Muito Raro Maior'), ('lendario', 'Lendário'), ('lendario_menor', 'Lendario Menor'), ('lendario_maior', 'Lendario Maior'), ('artefato', 'Artefato')], db_column='Raridade', default='incomum', max_length=50),
        ),
        migrations.AlterField(
            model_name='tbitemmagico',
            name='slot',
            field=models.CharField(choices=[('cabeca', 'Cabeça'), ('face_olhos', 'Face/Olhos'), ('rosto', 'Rosto'), ('pescoco', 'Pescoço'), ('costas', 'Costas'), ('torso', 'Torso'), ('bracos', 'Bracos'), ('maos', 'Mãos'), ('dedos', 'Dedos'), ('aneis', 'Aneis'), ('cintura', 'Cintura'), ('pes', 'Pés'), ('pele', 'Pele'), ('arma', 'Arma'), ('armadura', 'Armadura'), ('escudo', 'Escudo'), ('municao', 'Municao'), ('pocao', 'Pocao'), ('pergaminho', 'Pergaminho'), ('varinha', 'Varinha'), ('cajado_bastao', 'Cajado/Bastao'), ('veiculo', 'Veiculo'), ('flutuando', 'Flutuando'), ('acessorio', 'Acessorio'), ('edificacao', 'Edificacao'), ('empunhado', 'Empunhado'), ('objeto', 'Objeto'), ('item_menor', 'Item Menor')], db_column='Slot', default='objeto', max_length=50),
        ),
    ]
