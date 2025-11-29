 // Calling our requierments
const { Client, GatewayIntentBits, REST, Routes, SlashCommandBuilder, ActionRowBuilder, MessageFlags, TextDisplayBuilder, SeparatorBuilder, SeparatorSpacingSize, ButtonBuilder, ButtonStyle, ContainerBuilder } = require('discord.js');
 
 // Setting our variables
const TOKEN = 'YOUR_BOT_TOKEN';
const CLIENT_ID = 'YOUR_CLIENT_ID';
 
  const {
  Client,
  GatewayIntentBits,
  SlashCommandBuilder,
  Routes,
  EmbedBuilder,
  ButtonBuilder,
  ButtonStyle,
  ActionRowBuilder,
  REST
} = require('discord.js');

const client = new Client({
  intents: [GatewayIntentBits.Guilds]
});

// --------- REGISTER COMMAND ----------
const commands = [
  new SlashCommandBuilder()
    .setName('game')
    .setDescription('Send game info panel')
    .addStringOption(opt =>
      opt.setName('phone_link')
        .setDescription('Phone link')
        .setRequired(true)
    )
    .addStringOption(opt =>
      opt.setName('pc_link')
        .setDescription('PC link')
        .setRequired(true)
    )
    .addStringOption(opt =>
      opt.setName('loader_link')
        .setDescription('Loader link')
        .setRequired(true)
    )
    .addStringOption(opt =>
      opt.setName('sg_build_vers')
        .setDescription('Stumble Guys build version')
        .setRequired(true)
    )
    .addStringOption(opt =>
      opt.setName('stumble_hour_build_vers')
        .setDescription('Stumble Hour build version')
        .setRequired(true)
    )
    .toJSON(),
];

  // The bot sends the container after the command was used
client.on('interactionCreate', async interaction => {
  if (interaction.isChatInputCommand() && interaction.commandName === 'plan') {
    const components = [
        new ContainerBuilder()
            .addTextDisplayComponents(
                new TextDisplayBuilder().setContent("**Stumble Hour Downloads"),
            )
            .addSeparatorComponents(
                new SeparatorBuilder().setSpacing(SeparatorSpacingSize.Small).setDivider(true),
            )
            .setDescription(
`⏱️ **Last Updated:** <t:${now}:R>

🔹 **Stumble Guys build version:**  
${sg}

🔸 **Stumble Hour version:**  
${sh}`
      );
            .addSeparatorComponents(
                new SeparatorBuilder().setSpacing(SeparatorSpacingSize.Small).setDivider(true),
            )
            .addTextDisplayComponents(
                new TextDisplayBuilder().setContent("Phone Download\n:BF: Android"),
            )
            .addActionRowComponents(
                new ActionRowBuilder()
            .addComponents(
                        new ButtonBuilder()
                            .setStyle(ButtonStyle.Link)
                            .setLabel("Android Download(APK)")
                            .setURL(phone),
                    ),
            ),
];
            .addSeparatorComponents(
                new SeparatorBuilder().setSpacing(SeparatorSpacingSize.Small).setDivider(true),
            )
            .addTextDisplayComponents(
                new TextDisplayBuilder().setContent("PC Download\n:BF: Game Folder"),
            )
            .addActionRowComponents(
                new ActionRowBuilder()
            .addComponents(
                        new ButtonBuilder()
                            .setStyle(ButtonStyle.Link)
                            .setLabel("PC Download")
                            .setURL(pc),
                    ),
            ),
];
            .addSeparatorComponents(
                new SeparatorBuilder().setSpacing(SeparatorSpacingSize.Small).setDivider(true),
            )
            .addTextDisplayComponents(
                new TextDisplayBuilder().setContent("Loader DLL\n:BF: PC Loader"),
            )
            .addActionRowComponents(
                new ActionRowBuilder()
                    .addComponents(
                        new ButtonBuilder()
                            .setStyle(ButtonStyle.Link)
                            .setLabel("Loader Download")
                            .setURL(loader),
                    ),
            ),
];
 
  
