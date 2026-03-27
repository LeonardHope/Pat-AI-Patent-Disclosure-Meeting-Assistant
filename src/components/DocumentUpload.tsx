import { useCallback, useState } from "react";
import { useMeetingStore } from "../stores/meetingStore";
import { Upload, FileText, X } from "lucide-react";

export function DocumentUpload() {
  const documentNames = useMeetingStore((s) => s.documentNames);
  const addDocument = useMeetingStore((s) => s.addDocument);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);

  const uploadFile = useCallback(
    async (file: File) => {
      setUploading(true);
      try {
        const formData = new FormData();
        formData.append("file", file);
        const response = await fetch("/api/documents/upload", {
          method: "POST",
          body: formData,
        });
        if (response.ok) {
          const data = await response.json();
          addDocument(data.filename);
        }
      } finally {
        setUploading(false);
      }
    },
    [addDocument]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const files = Array.from(e.dataTransfer.files);
      files.forEach(uploadFile);
    },
    [uploadFile]
  );

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(e.target.files ?? []);
      files.forEach(uploadFile);
    },
    [uploadFile]
  );

  return (
    <div className="p-4">
      <h3 className="text-sm font-medium text-gray-300 mb-3">
        Pre-Meeting Documents
      </h3>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={`border-2 border-dashed rounded-lg p-6 text-center transition-colors ${
          dragging
            ? "border-blue-400 bg-blue-400/5"
            : "border-gray-700 hover:border-gray-600"
        }`}
      >
        <Upload
          className={`w-8 h-8 mx-auto mb-2 ${
            dragging ? "text-blue-400" : "text-gray-500"
          }`}
        />
        <p className="text-sm text-gray-400 mb-2">
          {uploading
            ? "Uploading..."
            : "Drag & drop disclosure documents here"}
        </p>
        <p className="text-xs text-gray-500 mb-3">PDF, DOCX, PPTX, or text</p>
        <label className="inline-flex items-center gap-2 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 rounded text-sm text-gray-300 cursor-pointer transition-colors">
          <input
            type="file"
            multiple
            accept=".pdf,.docx,.pptx,.txt,.md"
            onChange={handleFileInput}
            className="hidden"
          />
          Browse Files
        </label>
      </div>

      {documentNames.length > 0 && (
        <div className="mt-3 space-y-1.5">
          {documentNames.map((name, i) => (
            <div
              key={i}
              className="flex items-center gap-2 text-sm text-gray-300 bg-gray-800/50 rounded px-3 py-1.5"
            >
              <FileText className="w-4 h-4 text-gray-500" />
              <span className="truncate">{name}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
