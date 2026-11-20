// Figma BottomNav(3:195) 아이콘을 SVG로 옮김. 색은 currentColor라 글자색(선택·비선택)을 그대로 따라감
type IconProps = { size?: number }

const common = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
}

export function HomeIcon({ size = 26 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 26 26" aria-hidden="true">
      <path
        {...common}
        d="M3.25 11.375L13 3.25L22.75 11.375V21.6667C22.75 21.954 22.6359 22.2295 22.4327 22.4327C22.2295 22.6359 21.954 22.75 21.6667 22.75H16.25V16.25H9.75V22.75H4.33333C4.04602 22.75 3.77047 22.6359 3.5673 22.4327C3.36414 22.2295 3.25 21.954 3.25 21.6667V11.375Z"
      />
    </svg>
  )
}

export function ChallengeIcon({ size = 26 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 26 26" aria-hidden="true">
      <path {...common} d="M5.41667 22.75V4.33331" />
      <path {...common} d="M5.41667 4.33331H18.4167L15.7083 8.66665L18.4167 13H5.41667" />
    </svg>
  )
}

export function PairIcon({ size = 26 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 26 26" aria-hidden="true">
      <path
        {...common}
        d="M9.75 12.4583C11.8441 12.4583 13.5417 10.7607 13.5417 8.66667C13.5417 6.57259 11.8441 4.875 9.75 4.875C7.65592 4.875 5.95833 6.57259 5.95833 8.66667C5.95833 10.7607 7.65592 12.4583 9.75 12.4583Z"
      />
      <path {...common} d="M2.70833 21.6667C2.70833 17.7667 5.85 15.1667 9.75 15.1667C13.65 15.1667 16.7917 17.7667 16.7917 21.6667" />
      <path
        {...common}
        d="M18.4167 12.4584C19.9124 12.4584 21.125 11.2458 21.125 9.75002C21.125 8.25425 19.9124 7.04169 18.4167 7.04169C16.9209 7.04169 15.7083 8.25425 15.7083 9.75002C15.7083 11.2458 16.9209 12.4584 18.4167 12.4584Z"
      />
      <path {...common} d="M17.875 15.3834C20.9083 15.7084 23.2917 17.9834 23.2917 21.6667" />
    </svg>
  )
}

export function RecordIcon({ size = 26 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 26 26" aria-hidden="true">
      <path {...common} d="M5.41666 21.6667V11.9167" />
      <path {...common} d="M13 21.6667V5.41669" />
      <path {...common} d="M20.5833 21.6667V15.1667" />
    </svg>
  )
}

export function MyIcon({ size = 26 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 26 26" aria-hidden="true">
      <path
        {...common}
        d="M13 13C15.3932 13 17.3333 11.0599 17.3333 8.66665C17.3333 6.27341 15.3932 4.33331 13 4.33331C10.6068 4.33331 8.66666 6.27341 8.66666 8.66665C8.66666 11.0599 10.6068 13 13 13Z"
      />
      <path {...common} d="M4.33334 22.75C4.33334 17.9834 8.23334 15.1667 13 15.1667C17.7667 15.1667 21.6667 17.9834 21.6667 22.75" />
    </svg>
  )
}
