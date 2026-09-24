export const teamLogo = (team: string) =>
  `https://a.espncdn.com/i/teamlogos/nfl/500/${({ WSH: "wsh", LAR: "lar", LV: "lv" } as Record<string, string>)[team] || team.toLowerCase()}.png`;
