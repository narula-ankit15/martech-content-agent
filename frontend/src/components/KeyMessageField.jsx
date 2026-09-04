import { useState } from "react";

const SUGGESTIONS = [
  "2 & 3 BHK launch offer starting Rs 87 Lakhs, early possession",
  "Festive season offer: zero brokerage on premium homes",
  "Last few units left - book your dream home today",
  "New tower launch with 20+ lifestyle amenities",
  "Price hike alert: book before rates increase next month",
  "Exclusive site visit weekend with special previews",
  "Ready-to-move homes near Infosys Metro Station",
  "Refer a friend and earn exciting rewards",
];

function highlightMatch(text, query) {
  if (!query.trim()) return text;
  const index = text.toLowerCase().indexOf(query.trim().toLowerCase());
  if (index === -1) return text;
  return (
    <>
      {text.slice(0, index)}
      <strong>{text.slice(index, index + query.trim().length)}</strong>
      {text.slice(index + query.trim().length)}
    </>
  );
}

export default function KeyMessageField({ value, onChange }) {
  const [open, setOpen] = useState(false);

  const suggestions = value.trim()
    ? SUGGESTIONS.filter((s) => s.toLowerCase().includes(value.trim().toLowerCase()))
    : SUGGESTIONS;

  function pick(suggestion) {
    onChange(suggestion);
    setOpen(false);
  }

  return (
    <div className="key-message-field">
      <textarea
        className="filter-bar__input campaign-form__textarea"
        placeholder="Eg: 2 & 3 BHK launch offer starting Rs 87 Lakhs, early possession"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
      />
      {open && suggestions.length > 0 && (
        <div className="key-message-field__suggestions">
          {suggestions.map((s, i) => (
            <button
              key={i}
              type="button"
              className="key-message-field__suggestion"
              // onMouseDown (not onClick) fires before the textarea's onBlur,
              // so the pick registers before the dropdown closes.
              onMouseDown={(e) => {
                e.preventDefault();
                pick(s);
              }}
            >
              {highlightMatch(s, value)}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
