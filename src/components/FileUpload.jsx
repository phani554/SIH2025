import React, { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, File, Image, FileText } from 'lucide-react';

const FileUpload = ({ onFileSelect, selectedFile }) => {
  const onDrop = useCallback((acceptedFiles) => {
    if (acceptedFiles.length > 0) {
      onFileSelect(acceptedFiles[0]);
    }
  }, [onFileSelect]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/*': ['.jpeg', '.jpg', '.png', '.gif', '.bmp'],
      'application/pdf': ['.pdf'],
      'application/msword': ['.doc'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'text/plain': ['.txt'],
      'application/vnd.ms-excel': ['.xls'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx']
    },
    multiple: false,
    maxSize: 10 * 1024 * 1024 // 10MB
  });

  const getFileIcon = (file) => {
    if (!file) return <Upload size={48} />;
    
    const type = file.type;
    if (type.includes('image')) return <Image size={24} />;
    if (type.includes('pdf')) return <FileText size={24} />;
    return <File size={24} />;
  };

  return (
    <div className="upload-container">
      <div
        {...getRootProps()}
        className={`dropzone ${isDragActive ? 'active' : ''} ${selectedFile ? 'has-file' : ''}`}
      >
        <input {...getInputProps()} />
        
        <div className="upload-content">
          {selectedFile ? (
            <div className="selected-file">
              {getFileIcon(selectedFile)}
              <div className="file-details">
                <h3>{selectedFile.name}</h3>
                <p>{(selectedFile.size / 1024 / 1024).toFixed(2)} MB</p>
                <span className="file-type">{selectedFile.type || 'Unknown type'}</span>
              </div>
            </div>
          ) : (
            <div className="upload-prompt">
              <Upload size={48} />
              <h3>
                {isDragActive ? 'Drop your document here' : 'Upload KMRL Document'}
              </h3>
              <p>
                Drag & drop or click to select<br />
                <small>Supports: PDF, Images, Word docs, Excel, Text files (Max 10MB)</small>
              </p>
            </div>
          )}
        </div>
      </div>
      
      <div className="supported-formats">
        <h4>Supported Sources:</h4>
        <div className="format-tags">
          <span>📧 Email Attachments</span>
          <span>📱 WhatsApp PDFs</span>
          <span>📄 Scanned Documents</span>
          <span>🖼️ Engineering Drawings</span>
          <span>📊 Reports & Invoices</span>
          <span>📋 Policies & Circulars</span>
        </div>
      </div>
    </div>
  );
};

export default FileUpload;