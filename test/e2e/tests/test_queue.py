# Copyright Amazon.com Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You may
# not use this file except in compliance with the License. A copy of the
# License is located at
#
# 	 http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is distributed
# on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
# express or implied. See the License for the specific language governing
# permissions and limitations under the License.

"""Integration tests for the Queue API.
"""

import boto3
import pytest
import time
import logging
from typing import Dict, Tuple

from acktest.resources import random_suffix_name
from acktest.aws.identity import get_region
from acktest.k8s import resource as k8s
from e2e import service_marker, CRD_GROUP, CRD_VERSION, load_sqs_resource
from e2e.replacement_values import REPLACEMENT_VALUES
from e2e.bootstrap_resources import get_bootstrap_resources

RESOURCE_PLURAL = "queues"

CREATE_WAIT_AFTER_SECONDS = 5
UPDATE_WAIT_AFTER_SECONDS = 5
DELETE_WAIT_AFTER_SECONDS = 5

@service_marker
@pytest.mark.canary
class TestFunction:
    def get_queue(self, sqs_client, queue_name: str) -> dict:
        try:
            resp = sqs_client.get_queue_url(
                QueueName=queue_name
            )
            return resp

        except Exception as e:
            logging.debug(e)
            return None

    def queue_exists(self, sqs_client, queue_name: str) -> bool:
        return self.get_function(sqs_client, queue_name) is not None

    def test_smoke(self, sqs_client):
        resource_name = random_suffix_name("sqs-queue", 24)

        resources = get_bootstrap_resources()
        logging.debug(resources)

        replacements = REPLACEMENT_VALUES.copy()
        replacements["QUEUE_NAME"] = resource_name
        replacements["AWS_REGION"] = get_region()

        # Load Queue CR
        resource_data = load_sqs_resource(
            "queue",
            additional_replacements=replacements,
        )
        logging.debug(resource_data)

        # Create k8s resource
        ref = k8s.CustomResourceReference(
            CRD_GROUP, CRD_VERSION, RESOURCE_PLURAL,
            resource_name, namespace="default",
        )
        k8s.create_custom_resource(ref, resource_data)
        cr = k8s.wait_resource_consumed_by_controller(ref)

        assert cr is not None
        assert k8s.get_resource_exists(ref)

        time.sleep(CREATE_WAIT_AFTER_SECONDS)

        cr = k8s.wait_resource_consumed_by_controller(ref)

        # Check Queue exists
        exists = self.queue_exists(sqs_client, resource_name)
        assert exists

        # Delete k8s resource
        _, deleted = k8s.delete_custom_resource(ref)
        assert deleted is True

        time.sleep(DELETE_WAIT_AFTER_SECONDS)

        # Check Queue doesn't exist
        exists = self.queue_exists(sqs_client, resource_name)
        assert not exists