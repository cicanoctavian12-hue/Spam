 // Calling our requirements
const {
  Client,
  GatewayIntentBits,
  REST,
  Routes,
  SlashCommandBuilder,
  ActionRowBuilder,
  MessageFlags,
  TextDisplayBuilder,
  SeparatorBuilder,
  SeparatorSpacingSize,
  ButtonBuilder,
  ButtonStyle,
  ContainerBuilder
} = require('discord.js');

// Setting our variables
const TOKEN = "YOUR_BOT_TOKEN";
const CLIENT_ID = "YOUR_CLIENT_ID";

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
    .toJSON()
];

// --------- COMMAND HANDLER ----------
client.on("interactionCreate", async (interaction) => {
  if (!interaction.isChatInputCommand()) return;

  if (interaction.commandName === "game") {
    const phone = interaction.options.getString("phone_link");
    const pc = interaction.options.getString("pc_link");
    const loader = interaction.options.getString("loader_link");
    const sg = interaction.options.getString("sg_build_vers");
    const sh = interaction.options.getString("stumble_hour_build_vers");
    const now = Math.floor(Date.now() / 1000);

    const container = new ContainerBuilder()
      .addTextDisplayComponents(
        new TextDisplayBuilder().setContent("**Stumble Hour Downloads**")
      )
      .addSeparatorComponents(
        new SeparatorBuilder().setSpacing(SeparatorSpacingSize.Small).setDivider(true)
      )
      .addTextDisplayComponents(
        new TextDisplayBuilder().setContent(
          `⏱️ **Last Updated:** <t:${now}:D>\n\n` +
          `🔹 **Stumble Guys build version:** ${sg}\n\n` +
          `🔸 **Stumble Hour version:** ${sh}`
        )
      )
      .addSeparatorComponents(
        new SeparatorBuilder().setSpacing(SeparatorSpacingSize.Small).setDivider(true)
      )
      .addTextDisplayComponents(
        new TextDisplayBuilder().setContent("📱 Phone Download\n<:BF:1442503402968842371> Android")
      )
      .addActionRowComponents(
        new ActionRowBuilder().addComponents(
          new ButtonBuilder()
            .setStyle(ButtonStyle.Link)
            .setLabel("Android Download (APK)")
            .setURL(phone)
        )
      )
      .addSeparatorComponents(
        new SeparatorBuilder().setSpacing(SeparatorSpacingSize.Small).setDivider(true)
      )
      .addTextDisplayComponents(
        new TextDisplayBuilder().setContent("💻 PC Download\n<:BF:1442503402968842371> Game Folder")
      )
      .addActionRowComponents(
        new ActionRowBuilder().addComponents(
          new ButtonBuilder()
            .setStyle(ButtonStyle.Link)
            .setLabel("PC Download")
            .setURL(pc)
        )
      )
      .addSeparatorComponents(
        new SeparatorBuilder().setSpacing(SeparatorSpacingSize.Small).setDivider(true)
      )
      .addTextDisplayComponents(
        new TextDisplayBuilder().setContent("<:sg_check:1442516721658495056> Loader DLL\n<:BF:1442503402968842371> PC Loader")
      )
      .addActionRowComponents(
        new ActionRowBuilder().addComponents(
          new ButtonBuilder()
            .setStyle(ButtonStyle.Link)
            .setLabel("Loader Download")
            .setURL(loader)
        )
      );

    return interaction.reply({
      components: [container],
      flags: MessageFlags.IsComponentsV2
    });
  }
});

// --------- BOT LOGIN ----------
client.login(TOKEN);
