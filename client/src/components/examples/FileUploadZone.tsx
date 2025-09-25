import FileUploadZone from '../FileUploadZone';

export default function FileUploadZoneExample() {
  const handleFilesUpload = (files: File[]) => {
    console.log('Files uploaded:', files.map(f => f.name));
  };

  return (
    <div className="w-64">
      <FileUploadZone 
        onFilesUpload={handleFilesUpload} 
        isProcessing={false}
      />
    </div>
  );
}