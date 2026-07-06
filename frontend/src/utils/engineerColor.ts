const ENGINEER_COLORS = ['#06B6D4', '#A78BFA', '#F472B6', '#34D399', '#FB923C', '#E879F9', '#2DD4BF', '#FACC15'];

export function engineerColor(username: string): string {
  let h = 0;
  for (let i = 0; i < username.length; i++) h = (h * 31 + username.charCodeAt(i)) >>> 0;
  return ENGINEER_COLORS[h % ENGINEER_COLORS.length];
}
