import express from 'express'
import { internalDetectionsRouter } from './detections.js'

export const internalRouter = express.Router()

internalRouter.use('/detections', internalDetectionsRouter)


