/**
 * Brand Guidelines Color Palette (from LX_Brand_Guidelines.pdf)
 * These colors map to CSS variables defined in globals.css
 * Use these constants for inline styles where CSS variables aren't practical
 */

export const brandColors = {
  // Primary Brand Colors
  primaryBrandBlue: "var(--brand-primary-blue)",
  deepNavy: "var(--brand-deep-navy)",
  secondarySteel: "var(--brand-secondary-steel)",
  lightBlueTint: "var(--brand-light-blue-tint)",
  offWhiteBg: "var(--brand-off-white-bg)",
  primaryText: "var(--brand-primary-text)",
  secondaryText: "var(--brand-secondary-text)",
  deepBlue: "var(--brand-deep-blue-text)",

  // Status Colors
  success: "var(--brand-success)",
  successBg: "var(--brand-success-bg)",
  successText: "var(--brand-success-text)",
  successBorder: "var(--brand-success-border)",
  warning: "var(--brand-warning)",
  warningBg: "var(--brand-warning-bg)",
  warningText: "var(--brand-warning-text)",
  warningBorder: "var(--brand-warning-border)",
  error: "var(--brand-error)",
  errorBg: "var(--brand-error-bg)",
  errorText: "var(--brand-error-text)",
  errorBorder: "var(--brand-error-border)",
  info: "var(--brand-info)",
  infoBg: "var(--brand-info-bg)",
  infoText: "var(--brand-info-text)",
  infoBorder: "var(--brand-info-border)",

  // Neutral Shades
  borderGray: "var(--brand-border-gray)",
  disabledGray: "var(--brand-disabled-gray)",
  hoverGray: "var(--brand-hover-gray)",
  pureWhite: "var(--brand-pure-white)",
} as const;

// Raw hex values for cases where CSS variables don't work (e.g., some chart libraries)
export const brandColorsHex = {
  // Primary Brand Colors
  primaryBrandBlue: "#2F6FAE",
  deepNavy: "#1F2A37",
  secondarySteel: "#6B93C6",
  lightBlueTint: "#EAF2FB",
  offWhiteBg: "#F6F8FB",
  primaryText: "#111827",
  secondaryText: "#5A6169",
  deepBlue: "#1F3C52",

  // Status Colors
  success: "#2DA44E",
  successBg: "#D1FAE5",
  successText: "#065F46",
  successBorder: "#A7F3D0",
  warning: "#D97706",
  warningBg: "#FEF3C7",
  warningText: "#92400E",
  warningBorder: "#FDE68A",
  error: "#DC2626",
  errorBg: "#FEE2E2",
  errorText: "#991B1B",
  errorBorder: "#FECACA",
  info: "#2563EB",
  infoBg: "#DBEAFE",
  infoText: "#1E40AF",
  infoBorder: "#BFDBFE",

  // Neutral Shades
  borderGray: "#D1D5DB",
  disabledGray: "#9CA3AF",
  hoverGray: "#F3F4F6",
  pureWhite: "#FFFFFF",
} as const;

export type BrandColor = keyof typeof brandColors;
