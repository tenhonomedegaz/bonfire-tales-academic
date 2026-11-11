/* eslint-disable no-await-in-loop */
/* eslint-disable no-restricted-syntax */
import { container } from 'tsyringe';

import { IBaseJob, BotClient } from '@/shared/providers/SchedulerProvider/models/IBaseJob';
import { ILoggerProvider } from '@/shared/providers/LoggerProvider/models/ILoggerProvider';
import { bonfireChannels, shopList } from '@/config/bonfire';
import { RollShopItemsUseCase } from '@/modules/rpg/items/useCases/RollShopItemsUseCase';

interface JobData {
  guildId: string;
  [key: string]: any;
}

interface JobRequest {
  botClient: BotClient;
  logger: ILoggerProvider;
  jobData: JobData;
}

export class RollShopItemsJob implements IBaseJob {
  public static jobName = 'items-roll-shop';

  public async execute({ botClient, logger, jobData }: JobRequest): Promise<void> {
    try {
      const discordGuild = botClient.guilds.cache.find((guild) => guild.id === jobData.guildId);

      if (!discordGuild) {
        logger.log(
          'error',
          `Não foi possível localizar o servidor \`${jobData.guildId}\` no discord para continuar com o processo de rolar items agendado`,
        );
        return;
      }

      const logChannel = discordGuild.channels.cache.find(
        (channel) => channel.name === bonfireChannels.logChannelName,
      );

      if (!logChannel || !logChannel.isTextBased()) {
        logger.log(
          'error',
          `Não foi possível localizar o canal \`${bonfireChannels.logChannelName}\` no discord para continuar com o processo de rolar items agendado`,
        );
        return;
      }

      await logChannel.send(`Processo rolagem dos itens do shop iniciado`);

      for (const shop of shopList) {
        const shopChannel = discordGuild.channels.cache.find(
          (channel) => channel.name === shop.shopChannelName,
        );

        if (shopChannel && shopChannel.isTextBased()) {
          const rollShopItemsUseCase = container.resolve(RollShopItemsUseCase);

          const rolledItems = await rollShopItemsUseCase.execute({
            shopType: shop.shopType,
            itemsAmountToRoll: 5,
          });

          if (rolledItems.length >= 1) {
            await shopChannel.send(
              `Itens rolados (${shop.shopType}):\n${rolledItems
                .map((item) => item.name)
                .join('\n')}`,
            );
          }
        }
      }

      await logChannel.send(`Processo rolagem dos itens do shop finalizado`);
      await logChannel.send('-----------------------------------------------------------------');
    } catch (error) {
      logger.log('error', 'Erro job (RollShopItemsJob)', error);
    }
  }
}
