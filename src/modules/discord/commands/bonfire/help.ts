import { SlashCommandBuilder } from '@discordjs/builders';

import { IDiscordCommand } from '@/modules/discord/types';

const commandData = new SlashCommandBuilder()
  .setName('help')
  .setDescription('Mostra ajuda dos comandos do bot')
  .addStringOption((option) =>
    option
      .setName('categoria')
      .setDescription('Qual grupo de comandos voce quer ver?')
      .addChoices(
        { name: 'Missoes', value: 'missoes' },
        { name: 'Logs', value: 'logs' },
      )
      .setRequired(true),
  );

const missionHelp = [
  '**Comandos de missoes**',
  '',
  '`/missao-criar` - cria uma missao publica.',
  '`/missao-privada-criar` - cria uma missao privada.',
  '`/missao-controles` - abre o painel de iniciar, pausar, congelar e finalizar.',
  '`/missao-fila` - envia a fila de inscritos da missao no canal.',
  '`/missao-pick` - escolhe jogadores confirmados da fila.',
  '`/missao-add-player` - adiciona jogadores manualmente usando mencoes.',
  '`/missao-drop-player` - remove jogadores manualmente usando mencoes.',
  '`/missao-reagendar` - muda a data de uma missao ainda nao iniciada.',
  '`/editar-missao` - corrige a data/hora de eventos ja registrados.',
  '`/missao-rank` - Mestre/Staff edita os ranks permitidos da missao.',
  '`/missao-tags` - Mestre/Staff edita as tags da missao (ex: EVENTO).',
  '`/missao-excluir` - exclui uma missao.',
].join('\n');

const logsHelp = [
  '**Comandos de logs**',
  '',
  '`/meus-logs` - mostra seus logs cadastrados.',
  '`/update-logs` - atualiza seus logs relendo as planilhas cadastradas.',
  '`/remover-log` - remove um log seu pelo link da planilha.',
  '`/register-log` - Staff/Mod/Admin cadastra ou atualiza log de um jogador.',
  '`/ver-logs` - Staff/Mod/Admin ve os logs de um jogador.',
  '`/remover-log-jogador` - Staff/Mod/Admin remove log de outro jogador.',
  '`/logs-limpar-duplicados` - Admin raiz limpa registros duplicados.',
].join('\n');

const command: IDiscordCommand = {
  commandData,
  allowedRoles: [],
  cooldown: 3000,

  async execute(_bot, interaction) {
    const category = interaction.options.getString('categoria', true);
    await interaction.reply({
      content: category === 'missoes' ? missionHelp : logsHelp,
      ephemeral: true,
    });
  },
};

export default command;
