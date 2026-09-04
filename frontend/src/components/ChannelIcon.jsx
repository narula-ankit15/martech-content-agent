const CHANNEL_STYLE = {
  email: { bg: "var(--blue-icon-bg)", fg: "var(--blue-icon-fg)" },
  whatsapp: { bg: "var(--green-icon-bg)", fg: "var(--green-icon-fg)" },
};

function EmailGlyph({ color }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <rect x="3" y="5" width="18" height="14" rx="2.5" stroke={color} strokeWidth="1.8" />
      <path d="M4 7l8 6 8-6" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function WhatsAppGlyph({ color }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path
        d="M12 3.5a8 8 0 0 0-6.9 12l-1.1 4 4.2-1.1A8 8 0 1 0 12 3.5Z"
        stroke={color}
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
      <path
        d="M9 10.2c.5 2 2 3.5 4 4l1-1c.9.3 1.6.4 2 .4"
        stroke={color}
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function ChannelIcon({ channel, size = 32 }) {
  const style = CHANNEL_STYLE[channel] || CHANNEL_STYLE.email;
  return (
    <span
      className="channel-icon"
      style={{ width: size, height: size, background: style.bg }}
      title={channel}
    >
      {channel === "whatsapp" ? <WhatsAppGlyph color={style.fg} /> : <EmailGlyph color={style.fg} />}
    </span>
  );
}
