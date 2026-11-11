import { SlashCommandBuilder } from '@discordjs/builders';

import { IDiscordCommand } from '@/modules/discord/types';
import { isBotRootAdmin } from '@/modules/discord/util';

const commandData = new SlashCommandBuilder()
  .setName('desligar')
  .setDescription('Desliga o bot remotamente');

const command: IDiscordCommand = {
  commandData,
  allowedRoles: [],
  cooldown: 5000,
  rootAdminOnly: true,

  async execute(bot, interaction) {
    try {
      await interaction.deferReply({ ephemeral: true });

      if (!isBotRootAdmin(interaction.user.id)) {
        await interaction.editReply({
          content: 'Voce nao tem permissao para usar este comando.',
        });
        return;
      }

      await interaction.editReply({
        content: 'Desligando o bot... (Fechando processo no servidor hospedeiro)',
      });

      setTimeout(() => {
        if (process.env.pm_id) {
          const { exec } = require('child_process');
          exec(`pm2 stop ${process.env.pm_id}`);
        } else {
          process.exit(0);
        }
      }, 2000);
    } catch (error) {
      await interaction.editReply({
        content: `Erro ao tentar desligar: ${error}`,
      });
    }
  },
};

export default command;
