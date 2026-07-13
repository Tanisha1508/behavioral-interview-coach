'use client';

import { useState } from 'react';

export const DOC_LIMIT = 12000; // keeps each set_doc RPC under the 15KiB payload cap

export function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-left">
      <span className="text-foreground text-sm font-medium">{label}</span>
      {children}
    </label>
  );
}

// Paste-or-upload document field, shared by the setup form, the onboarding
// wizard, and the profile page. Upload runs the same lazy text extraction and
// character cap everywhere.
export function DocInput({
  label,
  value,
  onChange,
  placeholder,
  allowUpload = false,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  allowUpload?: boolean;
}) {
  const [status, setStatus] = useState('');
  const [fileName, setFileName] = useState('');
  const [showText, setShowText] = useState(false);

  const onFile = async (file: File | undefined) => {
    if (!file) return;
    setStatus('Reading file...');
    try {
      const { extractText } = await import('@/lib/extract-text');
      let text = (await extractText(file)).trim();
      if (!text) {
        setStatus('No text found in that file (is it a scanned PDF?). Paste instead.');
        return;
      }
      let note = '';
      if (text.length > DOC_LIMIT) {
        text = text.slice(0, DOC_LIMIT);
        note = ` (trimmed to ${DOC_LIMIT.toLocaleString()} characters)`;
      }
      onChange(text);
      setFileName(file.name);
      setShowText(false);
      setStatus(`${text.length.toLocaleString()} characters${note}`);
    } catch (err) {
      console.error('document extraction failed', err);
      setStatus('Could not read that file. Paste the text instead.');
    }
  };

  const remove = () => {
    onChange('');
    setFileName('');
    setStatus('');
    setShowText(false);
  };

  return (
    <Field label={label}>
      {allowUpload && !fileName && (
        <input
          type="file"
          accept=".pdf,.md,.txt"
          onChange={(e) => onFile(e.target.files?.[0])}
          className="text-muted-foreground file:border-input file:bg-background file:text-foreground text-xs file:mr-2 file:cursor-pointer file:rounded-md file:border file:px-2 file:py-1"
        />
      )}
      {fileName ? (
        <div className="border-input bg-background flex items-center gap-2 rounded-md border p-2 text-sm">
          <span className="text-foreground min-w-0 flex-1 truncate">
            {fileName} <span className="text-muted-foreground text-xs">{status}</span>
          </span>
          <button
            type="button"
            onClick={() => setShowText(!showText)}
            className="text-muted-foreground text-xs underline"
          >
            {showText ? 'Hide text' : 'View text'}
          </button>
          <button
            type="button"
            onClick={remove}
            className="text-muted-foreground text-xs underline"
          >
            Remove
          </button>
        </div>
      ) : (
        <>
          <textarea
            value={value}
            maxLength={DOC_LIMIT}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder}
            rows={4}
            className="border-input bg-background text-foreground rounded-md border p-2 text-sm"
          />
          {status && <span className="text-muted-foreground text-xs">{status}</span>}
        </>
      )}
      {fileName && showText && (
        <textarea
          value={value}
          maxLength={DOC_LIMIT}
          onChange={(e) => onChange(e.target.value)}
          rows={8}
          className="border-input bg-background text-foreground rounded-md border p-2 text-sm"
        />
      )}
    </Field>
  );
}
