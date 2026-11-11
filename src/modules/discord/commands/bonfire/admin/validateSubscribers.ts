import { SlashCommandBuilder } from '@discordjs/builders';

import { IDiscordCommand } from '@/modules/discord/types';
import { bonfireRoles, bonfireChannels } from '@/config/bonfire';
import { ValidadeMembersJob } from '@/modules/members/jobs/ValidadeMembersJob';

const commandData = new SlashCommandBuilder()
  .setName('colaboradores-validar')
  .setDescription('🔥 Valida a lista de colaboradores e os dias restantes de benefícios');

const command: IDiscordCommand = {
  commandData,
  allowedRoles: [bonfireRoles.adminRoleName],
  cooldown: 3 * 1000,
  async execute(bot, interaction) {
    try {
      await interaction.deferReply({ ephemeral: true });
      const { guild } = interaction;

      if (!guild) {
        await interaction.editReply({ content: `Não foi possível detectar o servidor do discord` });
        return;
      }

      const logChannel = guild.channels.cache.find(
        (channel) => channel.name === bonfireChannels.logChannelName,
      );

      if (!logChannel || !logChannel.isTextBased()) {
        await interaction.editReply({
          content: `Canal \`${bonfireChannels.logChannelName}\` inválido`,
        });
        return;
      }

      await bot.scheduler.runJob(ValidadeMembersJob.jobName, {
        guildId: guild.id,
        removeJobAfterRun: true,
      });

      await logChannel.send({
        content: `Processo de validação de membros iniciado por <@${interaction.user.id}>`,
      });

      await interaction.editReply({
        content: `Processo de validação de membros iniciado por <@${interaction.user.id}>`,
      });
    } catch (error) {
      bot.logger.log('error', `Erro no comando ${commandData.name}`, error);

      await interaction.editReply({
        content: `Erro ao executar processo de validação dos colaboradores`,
      });
    }
  },
};

export default command;
