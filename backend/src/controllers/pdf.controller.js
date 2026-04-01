const cloudinary = require('../config/cloudinary');
const File = require('../models/File.model'); 
const streamifier = require('streamifier');
const axios = require('axios'); // ADDED: Required to call Ritik's AI server

exports.uploadAndForward = async (req, res) => {
  try {
    if (!req.file) return res.status(400).json({ message: "No file uploaded" });

    // 1. Upload Buffer to Cloudinary
    const streamUpload = (req) => {
      return new Promise((resolve, reject) => {
        const stream = cloudinary.uploader.upload_stream(
          { 
            folder: "legalmind_pdfs", 
            resource_type: "raw" // Use "raw" for PDFs
          },
          (error, result) => {
            if (result) resolve(result);
            else reject(error);
          }
        );
        streamifier.createReadStream(req.file.buffer).pipe(stream);
      });
    };

    const cloudinaryResult = await streamUpload(req);

    // 2. Save Metadata to MongoDB
    const newFile = await File.create({
      fileName: req.file.originalname,
      cloudinaryUrl: cloudinaryResult.secure_url,
      public_id: cloudinaryResult.public_id,
      status: 'uploaded_successfully' // Changed status for testing
    });

    // 3. Hand-off to Ritik's Python AI Server (FastAPI)
    try {
      // Ritik ka IP: 192.168.1.14:8001
      // Baad mein process.env.AI_SERVER_URL se use karna production mein
      const pythonApiUrl = "http://192.168.1.14:8001/ai/ingest"; 
      
      console.log(`[Backend] Calling AI Engine at: ${pythonApiUrl}`);
      const pythonResponse = await axios.post(pythonApiUrl, {
        document_id: newFile._id.toString(), // Updated to exactly match Ritik's API model
        file_url: newFile.cloudinaryUrl      // Updated to exactly match Ritik's API model
      });
      
      console.log("[Backend] AI Engine Response:", pythonResponse.data);
    } catch (aiError) {
      console.error("[Backend] Failed to trigger AI Engine:", aiError.message);
      // Note: We're not throwing an error here, so sending the response to Harim continues
      // but you could mark status as 'failed_ingestion' later
    }

    // 4. Return success response with the Cloudinary URL
    res.status(200).json({
      message: "Cloudinary upload successful!",
      cloudinary_url: newFile.cloudinaryUrl,
      mongo_data: newFile
    });

  } catch (error) {
    console.error("Cloudinary Test Error:", error);
    res.status(500).json({ 
        message: "Cloudinary upload failed", 
        error: error.message 
    });
  }
};