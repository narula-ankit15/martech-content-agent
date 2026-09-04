import ChannelIcon from "./ChannelIcon";
import StatusPill from "./StatusPill";
import EditableTemplateName from "./EditableTemplateName";
import { contentTagLabel, previewBody, previewTitle } from "../contentPreview";

export default function ContentCard({ entry, onSelect, onDelete, onRename }) {
  function handleDelete(e) {
    e.stopPropagation();
    if (window.confirm(`Delete "${entry.template_name}"? This can't be undone.`)) {
      onDelete(entry);
    }
  }

  const tagLabel = contentTagLabel(entry);

  return (
    <div className={`content-card content-card--${entry.channel}`}>
      <div className="content-card__top">
        <ChannelIcon channel={entry.channel} />
        <div className="content-card__id">
          <EditableTemplateName entry={entry} onRenamed={onRename} textClassName="content-card__variant" />
          <span className="content-card__creative-id">
            {entry.template_id}
            {tagLabel && <span className="content-card__tag"> &middot; {tagLabel}</span>}
          </span>
        </div>
        {entry.status !== "approved" && <StatusPill status={entry.status} />}
        <button
          type="button"
          className="content-card__delete"
          onClick={handleDelete}
          aria-label="Delete this content"
          title="Delete"
        >
          🗑
        </button>
      </div>

      <h3 className="content-card__title">{previewTitle(entry)}</h3>
      <p className="content-card__body">{previewBody(entry)}</p>

      <div className="content-card__footer">
        <span className="content-card__date">
          {new Date(entry.created_at).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })}
        </span>
        <div className="content-card__actions">
          <button className="btn btn--ghost" onClick={() => onSelect(entry)}>
            View
          </button>
        </div>
      </div>
    </div>
  );
}
