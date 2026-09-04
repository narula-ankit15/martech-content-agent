import { useEffect, useState } from "react";
import ChannelIcon from "./ChannelIcon";
import StatusPill from "./StatusPill";
import EmailPreview from "./EmailPreview";
import SubjectLinePicker from "./SubjectLinePicker";
import WhatsAppPreview from "./WhatsAppPreview";
import EditableTemplateName from "./EditableTemplateName";
import { contentTagLabel } from "../contentPreview";

export default function DetailPanel({ entry, onClose, onRename, assetsById, businessName }) {
  const [selectedSubjectIndex, setSelectedSubjectIndex] = useState(0);

  useEffect(() => {
    // Reset to the saved-primary subject whenever a different entry is opened.
    setSelectedSubjectIndex(0);
  }, [entry?.creative_id]);

  if (!entry) return null;
  const isEmail = entry.channel === "email";
  const tagLabel = contentTagLabel(entry);

  return (
    <div className="detail-overlay" onClick={onClose}>
      <div className="detail-panel" onClick={(e) => e.stopPropagation()}>
        <div className="detail-panel__header">
          <ChannelIcon channel={entry.channel} size={40} />
          <div>
            <div className="detail-panel__creative-id">
              <EditableTemplateName entry={entry} onRenamed={onRename} textClassName="detail-panel__template-name" />
            </div>
            <div className="detail-panel__meta">
              {entry.project_id} &middot; {entry.campaign_id} &middot; {entry.template_id}
              {tagLabel && <> &middot; {tagLabel}</>}
            </div>
          </div>
          {entry.status !== "approved" && <StatusPill status={entry.status} />}
          <button className="detail-panel__close" onClick={onClose} aria-label="Close">
            &times;
          </button>
        </div>

        <div className="detail-panel__body">
          {isEmail ? (
            <>
              <SubjectLinePicker
                subjectLines={entry.content_json.subject_lines}
                selectedIndex={selectedSubjectIndex}
                onSelect={setSelectedSubjectIndex}
              />
              <EmailPreview
                subjectLines={entry.content_json.subject_lines}
                selectedSubjectIndex={selectedSubjectIndex}
                htmlBody={entry.content_json.html_body}
                assetsById={assetsById}
                creativeId={entry.creative_id}
              />
            </>
          ) : (
            <WhatsAppPreview
              draft={entry.content_json}
              imageUrl={entry.content_json.image_asset_id ? assetsById?.[entry.content_json.image_asset_id]?.url : null}
              businessName={businessName}
            />
          )}

          {entry.asset_ids.length > 0 && (
            <>
              <h4 className="detail-panel__asset-heading">Referenced assets</h4>
              <div className="detail-panel__asset-chips">
                {entry.asset_ids.map((id) => (
                  <span key={id} className="asset-chip">
                    {id}
                  </span>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
