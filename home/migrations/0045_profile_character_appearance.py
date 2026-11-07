from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0044_personagemitem_ca_formula'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='avatar_frame',
            field=models.CharField(blank=True, db_column='AvatarFrame', help_text='Efeito de borda do avatar.', max_length=40, null=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='banner_url',
            field=models.CharField(blank=True, db_column='BannerUrl', help_text='URL do banner do perfil. Aceita imagens animadas.', max_length=500, null=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='bio',
            field=models.TextField(blank=True, db_column='Bio', help_text='Texto curto exibido no perfil publico.', null=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='profile_effect',
            field=models.CharField(blank=True, db_column='ProfileEffect', help_text='Efeito visual do cartao de perfil.', max_length=40, null=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='profile_theme',
            field=models.CharField(db_column='ProfileTheme', default='bonfire', help_text='Tema visual do perfil.', max_length=40),
        ),
        migrations.AddField(
            model_name='tbpersonagem',
            name='banner_url',
            field=models.CharField(blank=True, db_column='BannerUrl', help_text='Link do banner visual da ficha. Aceita imagens animadas.', max_length=500, null=True),
        ),
        migrations.AddField(
            model_name='tbpersonagem',
            name='ficha_effect',
            field=models.CharField(blank=True, db_column='FichaEffect', help_text='Efeito visual do cabecalho da ficha.', max_length=40, null=True),
        ),
        migrations.AddField(
            model_name='tbpersonagem',
            name='ficha_theme',
            field=models.CharField(db_column='FichaTheme', default='bonfire', help_text='Tema visual da ficha.', max_length=40),
        ),
        migrations.AddField(
            model_name='tbpersonagem',
            name='foto_frame',
            field=models.CharField(blank=True, db_column='FotoFrame', help_text='Efeito de borda do retrato/token.', max_length=40, null=True),
        ),
    ]
