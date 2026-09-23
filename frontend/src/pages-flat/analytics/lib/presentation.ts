const monthFormatter = new Intl.DateTimeFormat("ru-RU", { month: "short", year: "2-digit", timeZone: "UTC" });
const dateFormatter = new Intl.DateTimeFormat("ru-RU", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
const percentageFormatter = new Intl.NumberFormat("ru-RU", { style: "percent", maximumFractionDigits: 1 });

export const formatAnalyticsMonth = (month: string) => monthFormatter.format(new Date(`${month}-01T00:00:00Z`));
export const formatAnalyticsDate = (date: string) => dateFormatter.format(new Date(date));
export const formatShare = (share: number) => percentageFormatter.format(share);
