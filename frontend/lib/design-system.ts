/**
 * Premium Design System
 *
 * A bold, modern design system inspired by the landing page aesthetics
 * featuring strong typography, vibrant colors, and professional polish.
 */

// ============================================================================
// COLOR PALETTE - Premium & Bold
// ============================================================================

export const colors = {
  // Primary colors - From landing page
  primary: {
    blue: '#5B8DBE',      // Landing page blue - primary CTAs
    blueHover: '#4A7AA8', // Deeper blue hover
    blueDark: '#3A6A98',  // Dark blue for emphasis
    blueLight: '#7BA5CE', // Light blue for backgrounds
  },

  // Neutral colors - From landing page
  neutral: {
    900: '#2D3748',       // Landing page dark gray - main headings
    800: '#374151',       // Very dark - subheadings
    700: '#4B5563',       // Dark - emphasized text
    600: '#6B7280',       // Landing page body text
    500: '#9CA3AF',       // Medium - muted text
    400: '#D1D5DB',       // Light - placeholders
    300: '#E5E7EB',       // Very light - borders
    200: '#F3F4F6',       // Lighter - dividers
    100: '#F9FAFB',       // Lightest - backgrounds
    50: '#FAFAFA',        // Almost white - secondary bg
  },

  // Accent colors - Status and highlights
  accent: {
    green: '#10B981',     // Success
    emerald: '#059669',   // Success dark
    yellow: '#F59E0B',    // Warning
    amber: '#D97706',     // Warning dark
    red: '#EF4444',       // Error/Danger
    rose: '#DC2626',      // Error dark
    purple: '#8B5CF6',    // Premium feature
    indigo: '#6366F1',    // Info/highlight
  },

  // Background colors - From landing page
  background: {
    primary: '#FFFFFF',
    secondary: '#F5F5F7',  // Landing page bg
    tertiary: '#EEEEEE',   // Landing page gradient
    subtle: '#FAFAFA',     // Subtle background
  },
} as const

// ============================================================================
// TYPOGRAPHY - Bold & Modern
// ============================================================================

export const typography = {
  // Display text - Hero sections
  display: {
    size: 'text-6xl md:text-7xl lg:text-8xl',
    weight: 'font-extrabold',
    leading: 'leading-none',
    tracking: 'tracking-tight',
  },

  // Heading levels - Strong hierarchy
  h1: {
    size: 'text-4xl md:text-5xl lg:text-6xl',
    weight: 'font-extrabold',
    leading: 'leading-tight',
    tracking: 'tracking-tight',
  },
  h2: {
    size: 'text-3xl md:text-4xl lg:text-5xl',
    weight: 'font-bold',
    leading: 'leading-tight',
    tracking: 'tracking-tight',
  },
  h3: {
    size: 'text-2xl md:text-3xl',
    weight: 'font-bold',
    leading: 'leading-snug',
  },
  h4: {
    size: 'text-xl md:text-2xl',
    weight: 'font-semibold',
    leading: 'leading-snug',
  },
  h5: {
    size: 'text-lg md:text-xl',
    weight: 'font-semibold',
    leading: 'leading-normal',
  },
  h6: {
    size: 'text-base md:text-lg',
    weight: 'font-semibold',
    leading: 'leading-normal',
  },

  // Body text - Clear and readable
  body: {
    large: {
      size: 'text-lg md:text-xl',
      weight: 'font-normal',
      leading: 'leading-relaxed',
    },
    DEFAULT: {
      size: 'text-base',
      weight: 'font-normal',
      leading: 'leading-relaxed',
    },
    small: {
      size: 'text-sm',
      weight: 'font-normal',
      leading: 'leading-relaxed',
    },
  },

  // Special text styles
  caption: {
    size: 'text-xs',
    weight: 'font-medium',
    transform: 'uppercase',
    tracking: 'tracking-wider',
  },

  label: {
    size: 'text-sm',
    weight: 'font-medium',
    leading: 'leading-normal',
  },
} as const

// ============================================================================
// SPACING - Generous & Balanced
// ============================================================================

export const spacing = {
  section: {
    sm: 'py-12',
    DEFAULT: 'py-16',
    lg: 'py-20',
    xl: 'py-24',
  },

  container: {
    sm: 'p-6',
    DEFAULT: 'p-8',
    lg: 'p-10',
    xl: 'p-12',
  },

  card: {
    sm: 'p-4',
    DEFAULT: 'p-6',
    lg: 'p-8',
  },

  gap: {
    xs: 'gap-2',
    sm: 'gap-4',
    DEFAULT: 'gap-6',
    lg: 'gap-8',
    xl: 'gap-12',
  },
} as const

// ============================================================================
// BORDER RADIUS - Modern & Consistent
// ============================================================================

export const radius = {
  sm: 'rounded-md',        // 6px - subtle
  DEFAULT: 'rounded-lg',   // 8px - standard
  lg: 'rounded-xl',        // 12px - prominent
  xl: 'rounded-2xl',       // 16px - very prominent
  full: 'rounded-full',
} as const

// ============================================================================
// SHADOWS - Depth & Elevation
// ============================================================================

export const shadows = {
  sm: 'shadow-sm',
  DEFAULT: 'shadow',
  md: 'shadow-md',
  lg: 'shadow-lg',
  xl: 'shadow-xl',
  '2xl': 'shadow-2xl',
  none: 'shadow-none',
} as const

// ============================================================================
// TRANSITIONS - Smooth & Professional
// ============================================================================

export const transitions = {
  fast: 'transition-all duration-150 ease-out',
  DEFAULT: 'transition-all duration-200 ease-out',
  slow: 'transition-all duration-300 ease-out',
} as const

// ============================================================================
// COMPONENT PATTERNS - Premium UI Elements
// ============================================================================

export const components = {
  // Button variants - Bold CTAs with landing page colors
  button: {
    primary: 'bg-[#5B8DBE] hover:bg-[#4A7AA8] text-white font-semibold px-6 py-3 rounded-lg shadow-md hover:shadow-lg transition-all duration-200',
    secondary: 'bg-white hover:bg-gray-50 text-[#2D3748] font-semibold px-6 py-3 rounded-lg border-2 border-gray-300 hover:border-gray-400 transition-all duration-200',
    outline: 'bg-transparent hover:bg-blue-50 text-[#5B8DBE] font-semibold px-6 py-3 rounded-lg border-2 border-[#5B8DBE] transition-all duration-200',
    ghost: 'bg-transparent hover:bg-gray-100 text-[#6B7280] font-medium px-4 py-2 rounded-lg transition-all duration-200',
  },

  // Card variants - Elevated surfaces
  card: {
    elevated: 'bg-white rounded-xl shadow-lg border border-gray-200 p-6',
    flat: 'bg-white rounded-lg border border-gray-200 p-6',
    ghost: 'bg-gray-50 rounded-lg p-6',
    gradient: 'bg-gradient-to-br from-white to-gray-50 rounded-xl border border-gray-200 p-6',
  },

  // Badge variants - Status indicators
  badge: {
    primary: 'inline-flex items-center px-3 py-1 rounded-full bg-blue-100 text-blue-700 text-xs font-semibold',
    success: 'inline-flex items-center px-3 py-1 rounded-full bg-green-100 text-green-700 text-xs font-semibold',
    warning: 'inline-flex items-center px-3 py-1 rounded-full bg-amber-100 text-amber-700 text-xs font-semibold',
    danger: 'inline-flex items-center px-3 py-1 rounded-full bg-red-100 text-red-700 text-xs font-semibold',
    neutral: 'inline-flex items-center px-3 py-1 rounded-full bg-gray-100 text-gray-700 text-xs font-semibold',
  },

  // Icon container variants
  iconContainer: {
    sm: 'w-10 h-10 rounded-lg flex items-center justify-center',
    DEFAULT: 'w-12 h-12 rounded-lg flex items-center justify-center',
    lg: 'w-14 h-14 rounded-xl flex items-center justify-center',
  },

  // Input fields
  input: 'w-full px-4 py-3 rounded-lg border-2 border-gray-300 focus:border-blue-500 focus:ring-4 focus:ring-blue-100 transition-all duration-200',
} as const

// ============================================================================
// ICON STYLING
// ============================================================================

export const iconStyles = {
  strokeWidth: 2,
  sizes: {
    xs: 'h-3 w-3',
    sm: 'h-4 w-4',
    DEFAULT: 'h-5 w-5',
    lg: 'h-6 w-6',
    xl: 'h-7 w-7',
    '2xl': 'h-8 w-8',
  },
} as const

// ============================================================================
// GRADIENTS - Modern backgrounds
// ============================================================================

export const gradients = {
  primary: 'bg-gradient-to-br from-blue-500 to-blue-700',
  secondary: 'bg-gradient-to-br from-gray-800 to-gray-900',
  subtle: 'bg-gradient-to-b from-white to-gray-50',
  vibrant: 'bg-gradient-to-br from-blue-500 via-purple-500 to-pink-500',
} as const

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

/**
 * Combine multiple class names
 */
export function cn(...classes: (string | undefined | null | false)[]): string {
  return classes.filter(Boolean).join(' ')
}

/**
 * Get text color based on variant
 */
export function getTextColor(variant: 'primary' | 'secondary' | 'muted' | 'accent' = 'primary'): string {
  switch (variant) {
    case 'primary':
      return 'text-gray-900'
    case 'secondary':
      return 'text-gray-700'
    case 'muted':
      return 'text-gray-500'
    case 'accent':
      return 'text-blue-600'
  }
}
