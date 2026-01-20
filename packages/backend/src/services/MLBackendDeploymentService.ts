/**
 * ML Backend Deployment Service
 * Business logic for ML backend deployment operations
 */
import { NotFoundError } from "../errors";
import { MLBackendDeploymentRepository } from "../repositories";

export class MLBackendDeploymentService {
  private deploymentRepo: MLBackendDeploymentRepository;

  constructor() {
    this.deploymentRepo = new MLBackendDeploymentRepository();
  }

  async getAvailableDeployments(userId: string) {
    return await this.deploymentRepo.findAvailableForUser(userId);
  }

  async getDeploymentById(id: number) {
    const deployment = await this.deploymentRepo.findById(id);

    if (!deployment) {
      throw new NotFoundError("ML Backend Deployment");
    }

    return deployment;
  }
}
