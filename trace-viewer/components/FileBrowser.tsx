import React, { useState, useEffect, useRef } from "react";
import { FolderOpen, FileJson, AlertCircle, Loader2, RefreshCw, Upload } from "lucide-react";
import { RunResult } from "../types";

interface FileInfo {
  name: string;
  lastModified: number;
  handle: FileSystemFileHandle;
}

interface FileBrowserProps {
  onFileLoaded: (data: RunResult, fileName: string) => void;
  // Lifted state props
  dirHandle: FileSystemDirectoryHandle | null;
  setDirHandle: (handle: FileSystemDirectoryHandle | null) => void;
  files: FileInfo[];
  setFiles: (files: FileInfo[]) => void;
  folderName: string;
  setFolderName: (name: string) => void;
  // Keyboard navigation
  selectedFileIndex: number;
  setSelectedFileIndex: (index: number) => void;
}

export type { FileInfo };

const FileBrowser: React.FC<FileBrowserProps> = ({ 
  onFileLoaded,
  dirHandle,
  setDirHandle,
  files,
  setFiles,
  folderName,
  setFolderName,
  selectedFileIndex,
  setSelectedFileIndex,
}) => {
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingFile, setIsLoadingFile] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Check if File System Access API is supported
  const isSupported = typeof window !== "undefined" && "showDirectoryPicker" in window;

  // Restore saved directory on mount
  useEffect(() => {
    if (!isSupported || dirHandle) return;

    const restoreSavedDirectory = async () => {
      try {
        const db = await openDB();
        const tx = db.transaction("settings", "readonly");
        const store = tx.objectStore("settings");
        const request = store.get("lastDirectory");
        
        const handle = await new Promise<FileSystemDirectoryHandle | undefined>((resolve, reject) => {
          request.onsuccess = () => resolve(request.result);
          request.onerror = () => reject(request.error);
        });

        if (handle) {
          // Verify we still have permission
          const permission = await (handle as any).queryPermission?.({ mode: "read" });
          if (permission === "granted" || permission === undefined) {
            setDirHandle(handle);
            setFolderName(handle.name);
            const jsonFiles = await scanDirectory(handle);
            setFiles(jsonFiles);
          }
        }
      } catch (e) {
        // Silently fail - user will just need to select folder manually
        console.debug("Could not restore saved directory:", e);
      }
    };

    restoreSavedDirectory();
  }, [isSupported]);

  // Helper to open/create IndexedDB
  const openDB = (): Promise<IDBDatabase> => {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open("TraceViewerDB", 1);
      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve(request.result);
      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result;
        if (!db.objectStoreNames.contains("settings")) {
          db.createObjectStore("settings");
        }
      };
    });
  };

  const scanDirectory = async (handle: FileSystemDirectoryHandle) => {
    const jsonFiles: FileInfo[] = [];

    for await (const entry of handle.values()) {
      if (entry.kind === "file" && entry.name.endsWith(".json")) {
        try {
          const file = await (entry as FileSystemFileHandle).getFile();
          jsonFiles.push({
            name: entry.name,
            lastModified: file.lastModified,
            handle: entry as FileSystemFileHandle,
          });
        } catch (e) {
          console.warn(`Failed to read file: ${entry.name}`, e);
        }
      }
    }

    // Sort by modified date, most recent first
    jsonFiles.sort((a, b) => b.lastModified - a.lastModified);
    return jsonFiles;
  };

  const handleSelectFolder = async () => {
    if (!isSupported) return;

    setError(null);
    setIsLoading(true);

    try {
      const handle = await window.showDirectoryPicker({ mode: "read" });
      setDirHandle(handle);
      setFolderName(handle.name);

      const jsonFiles = await scanDirectory(handle);
      setFiles(jsonFiles);

      if (jsonFiles.length === 0) {
        setError("No .json files found in this folder");
      }

      // Save directory handle for next time
      try {
        const db = await openDB();
        const tx = db.transaction("settings", "readwrite");
        await tx.objectStore("settings").put(handle, "lastDirectory");
      } catch (e) {
        console.debug("Could not save directory:", e);
      }
    } catch (e: any) {
      if (e.name !== "AbortError") {
        setError("Failed to open folder");
        console.error(e);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleRefresh = async () => {
    if (!dirHandle) return;

    setIsLoading(true);
    setError(null);

    try {
      const jsonFiles = await scanDirectory(dirHandle);
      setFiles(jsonFiles);

      if (jsonFiles.length === 0) {
        setError("No .json files found in this folder");
      }
    } catch (e) {
      setError("Failed to refresh folder");
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileClick = async (fileInfo: FileInfo, index: number) => {
    setSelectedFileIndex(index);
    setIsLoadingFile(fileInfo.name);
    setError(null);

    try {
      const file = await fileInfo.handle.getFile();
      const text = await file.text();
      const data = JSON.parse(text) as RunResult;

      // Basic validation
      if (!data.results || !data.meta) {
        throw new Error("Invalid trace file format");
      }

      onFileLoaded(data, fileInfo.name);
    } catch (e: any) {
      setError(`Failed to load ${fileInfo.name}: ${e.message}`);
      console.error(e);
    } finally {
      setIsLoadingFile(null);
    }
  };

  const formatDate = (timestamp: number) => {
    const date = new Date(timestamp);
    return date.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsLoadingFile(file.name);
    setError(null);

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const json = JSON.parse(e.target?.result as string);
        if (json.results && Array.isArray(json.results) && json.meta) {
          onFileLoaded(json as RunResult, file.name);
        } else {
          setError("Invalid file format: expected RunResult with 'results' array and 'meta' object.");
        }
      } catch (error: any) {
        setError(`Failed to parse JSON: ${error.message}`);
        console.error("Error parsing JSON:", error);
      } finally {
        setIsLoadingFile(null);
      }
    };
    reader.onerror = () => {
      setError("Failed to read file");
      setIsLoadingFile(null);
    };
    reader.readAsText(file);
    event.target.value = "";
  };

  // Unsupported browser - show upload button
  if (!isSupported) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-6 text-center">
        {/* Upload button */}
        <input
          type="file"
          accept=".json"
          ref={fileInputRef}
          className="hidden"
          onChange={handleFileUpload}
        />
        <button
          onClick={handleUploadClick}
          disabled={isLoadingFile !== null}
          className="flex items-center gap-2 px-4 py-2.5 bg-neutral-800 hover:bg-neutral-700 
                     rounded-lg transition-colors text-sm text-neutral-200 disabled:opacity-50"
        >
          {isLoadingFile ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Upload className="w-4 h-4" />
          )}
          Upload Trace
        </button>
        
        <p className="text-xs text-neutral-600 mt-4 max-w-xs">
          Tip: Chrome, Edge, or Opera support folder browsing to avoid opening files one by one
        </p>
        
        {error && (
          <div className="mt-4 px-4 py-2 bg-rose-950/30 border border-rose-900/50 rounded">
            <p className="text-xs text-rose-400">{error}</p>
          </div>
        )}
      </div>
    );
  }

  // No folder selected yet - show folder select and upload options
  if (!dirHandle) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-6 gap-4">
        <button
          onClick={handleSelectFolder}
          disabled={isLoading || isLoadingFile !== null}
          className="flex items-center gap-2 px-4 py-2.5 bg-neutral-800 hover:bg-neutral-700 
                     rounded-lg transition-colors text-sm text-neutral-200 disabled:opacity-50"
        >
          {isLoading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <FolderOpen className="w-4 h-4" />
          )}
          Select Folder
        </button>
        <p className="text-xs text-neutral-500 text-center">
          Navigate to the <span className="font-mono text-neutral-400">traces/</span> folder<br />
          in your project directory
        </p>
        
        <div className="flex items-center gap-3 w-full max-w-xs">
          <div className="flex-1 h-px bg-neutral-800"></div>
          <span className="text-xs text-neutral-500 uppercase">or</span>
          <div className="flex-1 h-px bg-neutral-800"></div>
        </div>
        
        {/* Upload button */}
        <input
          type="file"
          accept=".json"
          ref={fileInputRef}
          className="hidden"
          onChange={handleFileUpload}
        />
        <button
          onClick={handleUploadClick}
          disabled={isLoading || isLoadingFile !== null}
          className="flex items-center gap-2 px-4 py-2.5 bg-neutral-800 hover:bg-neutral-700 
                     rounded-lg transition-colors text-sm text-neutral-200 disabled:opacity-50"
        >
          {isLoadingFile ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Upload className="w-4 h-4" />
          )}
          Upload Trace
        </button>
        
        {error && (
          <div className="mt-2 px-4 py-2 bg-rose-950/30 border border-rose-900/50 rounded">
            <p className="text-xs text-rose-400">{error}</p>
          </div>
        )}
      </div>
    );
  }

  // Folder selected, show file list
  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Folder header */}
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-neutral-800 bg-neutral-900/50">
        <FolderOpen className="w-3.5 h-3.5 text-neutral-500 flex-shrink-0" />
        <span className="text-xs text-neutral-400 truncate flex-1" title={folderName}>
          {folderName}
        </span>
        <button
          onClick={handleRefresh}
          disabled={isLoading}
          className="p-1 hover:bg-neutral-800 rounded transition-colors"
          title="Refresh"
        >
          <RefreshCw className={`w-3.5 h-3.5 text-neutral-500 ${isLoading ? "animate-spin" : ""}`} />
        </button>
        <button
          onClick={handleSelectFolder}
          disabled={isLoading}
          className="text-xs text-neutral-500 hover:text-neutral-300 transition-colors"
        >
          Change
        </button>
      </div>

      {/* Error message */}
      {error && (
        <div className="px-4 py-2 bg-rose-950/30 border-b border-rose-900/50">
          <p className="text-xs text-rose-400">{error}</p>
        </div>
      )}

      {/* File list */}
      <div className="flex-1 overflow-y-auto">
        {isLoading && files.length === 0 ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-5 h-5 text-neutral-500 animate-spin" />
          </div>
        ) : files.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-center px-4">
            <p className="text-sm text-neutral-400">No .json files found</p>
          </div>
        ) : (
          files.map((file, index) => {
            const isLoadingThis = isLoadingFile === file.name;
            const isSelected = index === selectedFileIndex;
            return (
              <button
                key={file.name}
                onClick={() => handleFileClick(file, index)}
                disabled={isLoadingFile !== null}
                className={`w-full text-left px-4 py-3 border-b border-neutral-800/50 
                           transition-colors disabled:opacity-50
                           border-l-2 ${
                             isSelected 
                               ? 'bg-neutral-800 border-l-blue-500' 
                               : 'border-l-transparent hover:bg-neutral-800/50 hover:border-l-blue-500/50'
                           }`}
              >
                <div className="flex items-start gap-2.5">
                  {isLoadingThis ? (
                    <Loader2 className="w-4 h-4 text-blue-400 animate-spin flex-shrink-0 mt-0.5" />
                  ) : (
                    <FileJson className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-neutral-200 truncate" title={file.name}>
                      {file.name}
                    </p>
                    <p className="text-xs text-neutral-500 mt-0.5">
                      {formatDate(file.lastModified)}
                    </p>
                  </div>
                </div>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
};

export default FileBrowser;

